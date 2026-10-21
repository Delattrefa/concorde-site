"""
Règles du planning, partagées par les vues et la commande planning_taches :
répétitions, découpage en créneaux, notifications, mentions.
"""
import re
import uuid
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import format_html, urlize
from django.utils.safestring import mark_safe
from django.utils.text import Truncator

from .models import Canal, Creneau, Evenement, Message, Notification, Preferences, nom_membre

MAX_OCCURRENCES = 104  # deux ans de réunions hebdomadaires

REPETITIONS = [
    ("", "Pas de répétition"),
    ("hebdo", "Chaque semaine"),
    ("2semaines", "Toutes les deux semaines"),
    ("mois", "Chaque mois (même jour du mois)"),
]


def membres_actifs():
    return get_user_model().objects.filter(is_active=True).order_by("first_name", "last_name", "username")


# --- Répétitions ------------------------------------------------------------

def _decaler(moment, repetition, rang):
    if repetition == "hebdo":
        return moment + timedelta(weeks=rang)
    if repetition == "2semaines":
        return moment + timedelta(weeks=2 * rang)
    # Mensuelle : même jour du mois, mois sans ce jour sautés (ex. le 31)
    mois = moment.month - 1 + rang
    annee, mois = moment.year + mois // 12, mois % 12 + 1
    try:
        return moment.replace(year=annee, month=mois)
    except ValueError:
        return None


def dates_repetees(debut, repetition, jusquau):
    """Débuts des occurrences suivantes (sans la première)."""
    resultat, rang = [], 1
    while len(resultat) < MAX_OCCURRENCES - 1 and rang < 400:
        local = timezone.localtime(debut)
        suivant = _decaler(local.replace(tzinfo=None), repetition, rang)
        rang += 1
        if suivant is None:
            continue
        if suivant.date() > jusquau:
            break
        resultat.append(timezone.make_aware(suivant))
    return resultat


def repeter(evenement, repetition, jusquau):
    """Crée les occurrences suivantes d'un événement. Renvoie leur liste."""
    if not repetition or not jusquau:
        return []
    evenement.serie = uuid.uuid4()
    evenement.save(update_fields=["serie"])
    duree = evenement.fin - evenement.debut
    copies = []
    for debut in dates_repetees(evenement.debut, repetition, jusquau):
        copie = Evenement.objects.get(pk=evenement.pk)
        copie.pk = None
        copie.debut, copie.fin = debut, debut + duree
        copie.save()
        copies.append(copie)
    return copies


def appliquer_a_la_serie(evenement, champs):
    """Reporte titre, lieu, horaires... sur les occurrences suivantes,
    chacune gardant sa propre date."""
    debut_local, duree = timezone.localtime(evenement.debut), evenement.fin - evenement.debut
    suivantes = evenement.occurrences_suivantes().exclude(pk=evenement.pk)
    for occurrence in suivantes:
        for champ in champs:
            setattr(occurrence, champ, getattr(evenement, champ))
        jour = timezone.localtime(occurrence.debut).date()
        occurrence.debut = timezone.make_aware(datetime.combine(jour, debut_local.time()))
        occurrence.fin = occurrence.debut + duree
        occurrence.save()
    return list(suivantes)


# --- Créneaux ---------------------------------------------------------------

def decouper(evenement, minutes, besoin, libelle="", remplacer=False):
    """Découpe la plage de l'événement en créneaux de `minutes` minutes
    (le dernier peut être plus court)."""
    if remplacer:
        evenement.creneaux.filter(inscriptions__isnull=True).delete()
    pas = timedelta(minutes=minutes)
    debut, creneaux = evenement.debut, []
    while debut < evenement.fin:
        fin = min(debut + pas, evenement.fin)
        creneaux.append(Creneau(evenement=evenement, debut=debut, fin=fin, besoin=besoin, libelle=libelle))
        debut = fin
    return Creneau.objects.bulk_create(creneaux)


def copier_creneaux(modele, cibles):
    """Reproduit les créneaux de `modele` sur d'autres occurrences, aux
    mêmes heures par rapport au début de l'événement."""
    for cible in cibles:
        Creneau.objects.bulk_create([
            Creneau(evenement=cible, libelle=c.libelle, besoin=c.besoin,
                    debut=cible.debut + (c.debut - modele.debut), fin=cible.debut + (c.fin - modele.debut))
            for c in modele.creneaux.all()
        ])


# --- Notifications ----------------------------------------------------------

def notifier(destinataires, genre, texte, lien, exclure=None):
    """Crée une notification pour chaque destinataire (ids ou membres),
    sauf `exclure` (l'auteur de l'action). L'e-mail suit les préférences
    de chacun et part groupé avec la commande planning_taches."""
    ids = {getattr(d, "pk", d) for d in destinataires}
    if exclure is not None:
        ids.discard(exclure.pk)
    if not ids:
        return 0
    preferences = {p.membre_id: p for p in Preferences.objects.filter(membre_id__in=ids)}
    texte = Truncator(texte).chars(300)
    Notification.objects.bulk_create([
        Notification(
            destinataire_id=i, genre=genre, texte=texte, lien=lien,
            a_envoyer=(preferences.get(i) or Preferences()).veut_email(genre),
        )
        for i in ids
    ])
    return len(ids)


def notifier_evenement(evenement, action, auteur):
    """action : « créé », « modifié » ou « annulé »."""
    debut = timezone.localtime(evenement.debut)
    # Les trois types sont féminins : réunion, tâche, activité
    texte = f"{evenement.get_type_display()} {action}e par {nom_membre(auteur)} : {evenement.titre} ({debut:%d/%m à %H:%M})"
    if evenement.reserve_aux_invites:
        destinataires = evenement.participants()
    else:
        destinataires = membres_actifs().values_list("pk", flat=True)
    notifier(destinataires, Notification.EVENEMENT, texte, evenement.get_absolute_url(), exclure=auteur)


# --- Discussions ------------------------------------------------------------

RE_MENTION = re.compile(r"(^|\s)@([\w.+-]+)")


def mentions(texte):
    noms = {m.group(2).rstrip(".") for m in RE_MENTION.finditer(texte)}
    return list(get_user_model().objects.filter(username__in=noms, is_active=True))


def rendre_message(texte, membres_par_nom):
    """HTML d'un message : texte échappé, liens cliquables, mentions
    affichées avec le nom complet."""
    html = urlize(texte, nofollow=True, autoescape=True)

    def remplacer(m):
        membre = membres_par_nom.get(m.group(2).rstrip("."))
        if not membre:
            return m.group(0)
        return format_html('{}<span class="mention">@{}</span>', m.group(1), nom_membre(membre))

    html = RE_MENTION.sub(remplacer, html)
    return mark_safe(html.replace("\n", "<br>"))


def canal_de(evenement):
    canal, _ = Canal.objects.get_or_create(evenement=evenement, defaults={"nom": evenement.titre[:100]})
    return canal


def publier(canal, auteur, texte):
    message = Message.objects.create(canal=canal, auteur=auteur, texte=texte)
    mentionnes = mentions(texte)
    if mentionnes:
        message.mentions.set(mentionnes)
    extrait = Truncator(texte).chars(120)
    lien = canal.get_absolute_url()
    ou = f"« {canal.nom} »"
    notifier(mentionnes, Notification.MENTION, f"{nom_membre(auteur)} vous a mentionné dans {ou} : {extrait}",
             lien, exclure=auteur)
    if canal.evenement_id:
        # Fil d'un événement : ses participants, et ceux qui y ont écrit
        concernes = canal.evenement.participants()
        concernes |= set(canal.messages.exclude(auteur=None).values_list("auteur", flat=True))
        concernes -= {m.pk for m in mentionnes}
        notifier(concernes, Notification.MESSAGE, f"{nom_membre(auteur)} dans {ou} : {extrait}", lien, exclure=auteur)
    return message


def message_json(message, membres_par_nom, user):
    auteur = message.auteur
    return {
        "id": message.pk,
        "auteur": nom_membre(auteur),
        "initiales": "".join(p[0] for p in nom_membre(auteur).split()[:2]).upper(),
        "moi": auteur is not None and auteur.pk == user.pk,
        "heure": f"{timezone.localtime(message.cree_le):%d/%m %H:%M}",
        "html": str(rendre_message(message.texte, membres_par_nom)),
    }


def membres_par_nom():
    return {m.username: m for m in membres_actifs()}
