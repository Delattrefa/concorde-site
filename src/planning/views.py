"""
Vues du planning : agenda (mois, semaine, jour, liste), événements,
créneaux et inscriptions, couverture des besoins, disponibilités,
invitations. Toutes réservées aux membres connectés.
"""
import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import F, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from calendrier.models import Activite

from . import grille, services
from .forms import (
    CreneauForm,
    DecouperForm,
    DisponibiliteForm,
    EvenementForm,
    InviterForm,
    PlagesFormSet,
    TacheForm,
)
from .views_discussion import contexte_discussion
from .models import (
    Creneau,
    Disponibilite,
    Evenement,
    Inscription,
    Invitation,
    Notification,
    Sondage,
    est_responsable,
    nom_membre,
)

MOIS = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
TYPES = dict(Evenement.TYPES)


# --- Outils -----------------------------------------------------------------

def _debut_du_jour(jour):
    return timezone.make_aware(datetime.combine(jour, time.min))


def _jours_couverts(evenement):
    """Dates (locales) occupées par l'événement, 60 au plus."""
    premier = timezone.localtime(evenement.debut).date()
    dernier = timezone.localtime(evenement.fin - timedelta(microseconds=1)).date()
    return [premier + timedelta(days=i) for i in range(min((dernier - premier).days + 1, 60))]


def _avec_creneaux(requete):
    return requete.prefetch_related(
        Prefetch("creneaux", queryset=Creneau.objects.avec_effectif().prefetch_related("inscriptions__membre"))
    )


def _manque(evenement):
    return sum(max(0, c.besoin - c.nb_inscrits) for c in evenement.creneaux.all())


def _repartir_inscrits(creneau, user):
    """Membres inscrits d'un côté, noms libres (sans compte) de l'autre."""
    inscriptions = list(creneau.inscriptions.all())
    creneau.inscrits = [i.membre for i in inscriptions if i.membre_id]
    creneau.externes = [i for i in inscriptions if not i.membre_id]
    creneau.je_suis_inscrit = any(m.pk == user.pk for m in creneau.inscrits)


def _preparer_creneaux(evenement, user):
    """Créneaux prêts à afficher : inscrits, place libre, inscription."""
    creneaux = list(evenement.creneaux.all())
    for c in creneaux:
        _repartir_inscrits(c, user)
        c.manque = max(0, c.besoin - c.nb_inscrits)
    return creneaux


def _type_filtre(request):
    valeur = request.GET.get("type", "")
    return valeur if valeur in TYPES else ""


def _entrees(user, premier, dernier, type_filtre=""):
    """Événements du planning et activités du calendrier du site, rangés
    par jour : {date: [entrée, ...]}."""
    debut, fin = _debut_du_jour(premier), _debut_du_jour(dernier + timedelta(days=1))
    requete = Evenement.objects.visibles_par(user).filter(debut__lt=fin, fin__gt=debut)
    if type_filtre:
        requete = requete.filter(type=type_filtre)
    par_jour = defaultdict(list)
    for e in _avec_creneaux(requete):
        manque = _manque(e)
        for jour in _jours_couverts(e):
            if premier <= jour <= dernier:
                par_jour[jour].append({
                    "objet": e, "type": e.type, "titre": e.titre, "url": e.get_absolute_url(),
                    "heure": timezone.localtime(e.debut).strftime("%H:%M") if jour == _jours_couverts(e)[0] else "",
                    "annule": e.annule, "manque": manque, "tri": timezone.localtime(e.debut).time(),
                })
    if not type_filtre:
        # Activités du calendrier du site (publiques et privées), pour mémoire
        for a in Activite.objects.filter(date_debut__lte=dernier, date_fin__gte=premier):
            jour = max(a.date_debut, premier)
            while jour <= min(a.date_fin, dernier):
                par_jour[jour].append({
                    "type": "site", "titre": a.nom, "url": a.get_absolute_url(), "heure": "",
                    "annule": False, "manque": 0, "tri": time.min,
                })
                jour += timedelta(days=1)
    for entrees in par_jour.values():
        entrees.sort(key=lambda x: x["tri"])
    return par_jour


def _contexte_agenda(request, vue, jour):
    type_filtre = _type_filtre(request)
    return {
        "vue": vue, "jour": jour, "aujourdhui": timezone.localdate(), "types": Evenement.TYPES,
        "type_filtre": type_filtre, "suffixe": f"?type={type_filtre}" if type_filtre else "",
        "est_responsable": est_responsable(request.user),
    }


def _date_ou_404(annee, mois, jour=1):
    try:
        return date(annee, mois, jour)
    except ValueError:
        raise Http404


# --- Agenda -----------------------------------------------------------------

@login_required
def mois(request, annee=None, mois=None):
    aujourdhui = timezone.localdate()
    premier = _date_ou_404(annee or aujourdhui.year, mois or aujourdhui.month)
    dernier = premier.replace(day=calendar.monthrange(premier.year, premier.month)[1])
    debut_grille = premier - timedelta(days=premier.weekday())
    fin_grille = dernier + timedelta(days=6 - dernier.weekday())
    contexte = _contexte_agenda(request, "mois", premier)
    entrees = _entrees(request.user, debut_grille, fin_grille, contexte["type_filtre"])
    semaines, jour = [], debut_grille
    while jour <= fin_grille:
        semaines.append([{"date": j, "dans_le_mois": j.month == premier.month, "entrees": entrees.get(j, [])}
                         for j in (jour + timedelta(days=i) for i in range(7))])
        jour += timedelta(days=7)
    precedent = (premier - timedelta(days=1)).replace(day=1)
    suivant = dernier + timedelta(days=1)
    contexte.update({
        "titre": f"{MOIS[premier.month].capitalize()} {premier.year}", "semaines": semaines, "jours_semaine": JOURS,
        "url_precedent": reverse("planning:mois", args=[precedent.year, precedent.month]),
        "url_suivant": reverse("planning:mois", args=[suivant.year, suivant.month]),
    })
    return render(request, "planning/agenda_mois.html", contexte)


@login_required
def semaine(request, annee, mois, jour):
    lundi = _date_ou_404(annee, mois, jour)
    lundi -= timedelta(days=lundi.weekday())
    dimanche = lundi + timedelta(days=6)
    contexte = _contexte_agenda(request, "semaine", lundi)
    entrees = _entrees(request.user, lundi, dimanche, contexte["type_filtre"])
    jours = [{"date": j, "nom": JOURS[i], "entrees": entrees.get(j, [])}
             for i, j in enumerate(lundi + timedelta(days=n) for n in range(7))]
    precedent, suivant = lundi - timedelta(days=7), lundi + timedelta(days=7)
    contexte.update({
        "titre": f"Semaine du {lundi.day} {MOIS[lundi.month]} au {dimanche.day} {MOIS[dimanche.month]} {dimanche.year}",
        "jours": jours,
        "url_precedent": reverse("planning:semaine", args=[precedent.year, precedent.month, precedent.day]),
        "url_suivant": reverse("planning:semaine", args=[suivant.year, suivant.month, suivant.day]),
    })
    return render(request, "planning/agenda_semaine.html", contexte)


@login_required
def jour(request, annee, mois, jour):
    le_jour = _date_ou_404(annee, mois, jour)
    contexte = _contexte_agenda(request, "jour", le_jour)
    entrees = _entrees(request.user, le_jour, le_jour, contexte["type_filtre"]).get(le_jour, [])
    evenements = [e["objet"] for e in entrees if "objet" in e]
    for e in evenements:
        e.liste_creneaux = _preparer_creneaux(e, request.user)
        e.modifiable = e.peut_modifier(request.user)
        e.est_passe = e.fin < timezone.now()
    precedent, suivant = le_jour - timedelta(days=1), le_jour + timedelta(days=1)
    contexte.update({
        "titre": f"{JOURS[le_jour.weekday()].capitalize()} {le_jour.day} {MOIS[le_jour.month]} {le_jour.year}",
        "evenements": evenements,
        "activites_site": [e for e in entrees if e["type"] == "site"],
        "disponibles": Disponibilite.objects.filter(date=le_jour).select_related("membre"),
        "membres": services.membres_actifs() if any(e.modifiable for e in evenements) else [],
        "url_precedent": reverse("planning:jour", args=[precedent.year, precedent.month, precedent.day]),
        "url_suivant": reverse("planning:jour", args=[suivant.year, suivant.month, suivant.day]),
    })
    return render(request, "planning/agenda_jour.html", contexte)


@login_required
def liste(request):
    contexte = _contexte_agenda(request, "liste", timezone.localdate())
    mes_engagements = request.GET.get("moi") == "1"
    debut = _debut_du_jour(timezone.localdate())
    requete = Evenement.objects.visibles_par(request.user).filter(fin__gt=debut, debut__lt=debut + timedelta(days=90))
    if contexte["type_filtre"]:
        requete = requete.filter(type=contexte["type_filtre"])
    if mes_engagements:
        moi = request.user
        requete = requete.filter(
            Q(createur=moi) | Q(invitations__membre=moi, invitations__statut__in=[Invitation.EN_ATTENTE, Invitation.ACCEPTEE])
            | Q(creneaux__inscriptions__membre=moi)
        ).distinct()
    groupes = defaultdict(list)
    for e in _avec_creneaux(requete):
        e.manque = _manque(e)
        e.mes_creneaux = [c for c in e.creneaux.all() if any(i.membre_id == request.user.pk for i in c.inscriptions.all())]
        groupes[timezone.localtime(e.debut).date()].append(e)
    contexte.update({
        "titre": "Mes engagements" if mes_engagements else "Planning des 3 prochains mois",
        "mes_engagements": mes_engagements,
        "groupes": [{"date": d, "nom": JOURS[d.weekday()], "evenements": groupes[d]} for d in sorted(groupes)],
        "suffixe": "?" + "&".join(p for p in [
            f"type={contexte['type_filtre']}" if contexte["type_filtre"] else "", "moi=1" if mes_engagements else ""
        ] if p),
    })
    return render(request, "planning/agenda_liste.html", contexte)


@login_required
def plannings(request):
    """Tous les plannings en cours : événements à venir ou en cours qui
    ont des tâches ou créneaux, pour y accéder sans passer par l'agenda."""
    requete = (Evenement.objects.visibles_par(request.user)
               .filter(fin__gt=timezone.now(), creneaux__isnull=False).distinct().order_by("debut"))
    if request.GET.get("moi") == "1":
        requete = requete.filter(createur=request.user)
    # Une série (ménage chaque lundi…) n'apparaît qu'une fois : sa prochaine date
    evenements, series = [], {}
    for e in _avec_creneaux(requete.select_related("createur")):
        if e.serie and e.serie in series:
            series[e.serie].dates_suivantes.append(e)
            continue
        e.dates_suivantes = []
        if e.serie:
            series[e.serie] = e
        evenements.append(e)
    for e in evenements:
        creneaux = e.creneaux.all()
        e.besoin = sum(c.besoin for c in creneaux)
        e.pourvu = sum(min(c.nb_inscrits, c.besoin) for c in creneaux)
        e.manque = e.besoin - e.pourvu
        e.taches = sorted({c.libelle or "Bénévoles" for c in creneaux})
        e.mes_creneaux = [c for c in creneaux if any(i.membre_id == request.user.pk for i in c.inscriptions.all())]
        e.modifiable = e.peut_modifier(request.user)
    return render(request, "planning/plannings.html", {
        "evenements": evenements, "mes_plannings": request.GET.get("moi") == "1",
    })


# --- Événements -------------------------------------------------------------

def _evenement_visible(request, pk):
    evenement = Evenement.objects.visibles_par(request.user).filter(pk=pk).first()
    if evenement is None:
        raise Http404
    return evenement


def _evenement_modifiable(request, pk):
    evenement = _evenement_visible(request, pk)
    if not evenement.peut_modifier(request.user):
        raise PermissionDenied
    return evenement


def _inviter(evenement, ids, auteur):
    deja = set(evenement.invitations.values_list("membre", flat=True))
    nouveaux = set(ids) - deja
    Invitation.objects.bulk_create([Invitation(evenement=evenement, membre_id=i) for i in nouveaux])
    debut = timezone.localtime(evenement.debut)
    services.notifier(
        nouveaux, Notification.INVITATION,
        f"{nom_membre(auteur)} vous invite : {evenement.titre} ({debut:%d/%m à %H:%M})",
        evenement.get_absolute_url(), exclure=auteur,
    )
    return nouveaux


@login_required
def evenement_ajouter(request):
    initial = {}
    try:
        jour_choisi = date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        jour_choisi = None
    if jour_choisi:
        initial["debut"] = datetime.combine(jour_choisi, time(19, 0))
        initial["fin"] = datetime.combine(jour_choisi, time(21, 0))
    if request.GET.get("type") in TYPES:
        initial["type"] = request.GET["type"]
    # Depuis un sondage de date clôturé : date retenue, participants invités
    sondage = None
    if request.GET.get("sondage"):
        sondage = get_object_or_404(Sondage, pk=request.GET["sondage"], type=Sondage.TYPE_DATE)
        option = sondage.options.filter(pk=request.GET.get("option")).first()
        initial.update({"titre": sondage.titre, "description": sondage.description, "type": Evenement.TYPE_REUNION})
        if option and option.debut:
            initial["debut"] = timezone.localtime(option.debut).replace(tzinfo=None)
            initial["fin"] = timezone.localtime(option.fin or option.debut + timedelta(hours=2)).replace(tzinfo=None)
        initial["inviter_membres"] = list(
            get_user_model().objects.filter(votes_planning__option__sondage=sondage).distinct().values_list("pk", flat=True)
        )

    form = EvenementForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            evenement = form.save(commit=False)
            evenement.createur = request.user
            evenement.save()
            occurrences = [evenement] + services.repeter(
                evenement, form.cleaned_data.get("repetition"), form.cleaned_data.get("repeter_jusquau")
            )
            if form.cleaned_data.get("duree_creneaux"):
                services.decouper(evenement, form.cleaned_data["duree_creneaux"], form.cleaned_data.get("besoin_creneaux") or 1)
                services.copier_creneaux(evenement, occurrences[1:])
            invites = form.invites()
            for occurrence in occurrences:
                Invitation.objects.bulk_create([Invitation(evenement=occurrence, membre_id=i) for i in invites])
            if sondage and not sondage.evenement_id:
                sondage.evenement = evenement
                sondage.save(update_fields=["evenement"])
        services.notifier_evenement(evenement, "créé", request.user)
        if invites:
            debut = timezone.localtime(evenement.debut)
            serie = f" (et {len(occurrences) - 1} dates suivantes)" if len(occurrences) > 1 else ""
            services.notifier(invites, Notification.INVITATION,
                              f"{nom_membre(request.user)} vous invite : {evenement.titre} ({debut:%d/%m à %H:%M}){serie}",
                              evenement.get_absolute_url(), exclure=request.user)
        texte = f"« {evenement.titre} » ajouté au planning"
        if len(occurrences) > 1:
            texte += f", avec {len(occurrences) - 1} répétition{'s' if len(occurrences) > 2 else ''}"
        if evenement.type == Evenement.TYPE_ACTIVITE and not evenement.creneaux.exists():
            # Une activité s'organise par tâches : on enchaîne sur le tableau
            messages.success(request, texte + ". Ajoutez maintenant les tâches et leurs horaires.")
            return redirect("planning:tache_ajouter", pk=evenement.pk)
        messages.success(request, texte + ".")
        return redirect(evenement)
    return render(request, "planning/evenement_form.html", {"form": form, "sondage": sondage})


@login_required
def evenement_modifier(request, pk):
    evenement = _evenement_modifiable(request, pk)
    form = EvenementForm(request.POST or None, instance=evenement)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            evenement = form.save()
            invites = form.invites()
            if form.cleaned_data.get("appliquer_serie"):
                suivantes = services.appliquer_a_la_serie(
                    evenement, ["type", "titre", "description", "lieu", "reserve_aux_invites"]
                )
                for occurrence in suivantes:
                    deja = set(occurrence.invitations.values_list("membre", flat=True))
                    Invitation.objects.bulk_create([Invitation(evenement=occurrence, membre_id=i) for i in invites - deja])
        if invites:
            _inviter(evenement, invites, request.user)
        if form.changed_data:
            services.notifier_evenement(evenement, "modifié", request.user)
        messages.success(request, "Modifications enregistrées.")
        return redirect(evenement)
    return render(request, "planning/evenement_form.html", {"form": form, "evenement": evenement})


@login_required
def evenement(request, pk):
    evenement = _evenement_visible(request, pk)
    evenement = _avec_creneaux(Evenement.objects.filter(pk=evenement.pk)).select_related("createur").get()
    moi = request.user
    creneaux = _preparer_creneaux(evenement, moi)
    invitations = list(evenement.invitations.select_related("membre").order_by("statut", "membre__first_name"))
    peut_modifier = evenement.peut_modifier(moi)
    return render(request, "planning/evenement_detail.html", {
        **contexte_discussion(services.canal_de(evenement), moi),
        "evenement": evenement,
        "creneaux": creneaux,
        "grille": grille.construire(creneaux),
        "vue_liste": request.GET.get("vue") == "liste",
        "manque": sum(c.manque for c in creneaux),
        "invitations": invitations,
        "mon_invitation": next((i for i in invitations if i.membre_id == moi.pk), None),
        "compteurs_invitations": {s: sum(1 for i in invitations if i.statut == s) for s, _ in Invitation.STATUTS},
        "peut_modifier": peut_modifier,
        "est_responsable": est_responsable(moi),
        "membres": services.membres_actifs() if peut_modifier else [],
        "inviter_form": InviterForm() if peut_modifier else None,
        "nb_occurrences_suivantes": evenement.occurrences_suivantes().count() - 1 if evenement.serie else 0,
        "sondages": evenement.sondages.all(),
        "passe": evenement.fin < timezone.now(),
    })


def _portee(request, evenement):
    if request.POST.get("portee") == "suivantes" and evenement.serie:
        return list(evenement.occurrences_suivantes())
    return [evenement]


@login_required
def evenement_annuler(request, pk):
    evenement = _evenement_modifiable(request, pk)
    if request.method == "POST":
        retablir = request.POST.get("retablir") == "1"
        cibles = _portee(request, evenement)
        Evenement.objects.filter(pk__in=[e.pk for e in cibles]).update(annule=not retablir)
        evenement.refresh_from_db()
        services.notifier_evenement(evenement, "rétabli" if retablir else "annulé", request.user)
        texte = "rétabli" if retablir else "annulé"
        messages.success(request, f"Événement {texte}" + (f" ({len(cibles)} dates)." if len(cibles) > 1 else "."))
        return redirect(evenement)
    return render(request, "planning/evenement_confirmer.html", {
        "evenement": evenement, "action": "annuler",
        "nb_occurrences_suivantes": evenement.occurrences_suivantes().count() - 1 if evenement.serie else 0,
    })


@login_required
def evenement_supprimer(request, pk):
    evenement = _evenement_modifiable(request, pk)
    if request.method == "POST":
        cibles = _portee(request, evenement)
        titre = evenement.titre
        Evenement.objects.filter(pk__in=[e.pk for e in cibles]).delete()
        messages.success(request, f"« {titre} » supprimé" + (f" ({len(cibles)} dates)." if len(cibles) > 1 else "."))
        return redirect("planning:accueil")
    return render(request, "planning/evenement_confirmer.html", {
        "evenement": evenement, "action": "supprimer",
        "nb_occurrences_suivantes": evenement.occurrences_suivantes().count() - 1 if evenement.serie else 0,
    })


# --- Invitations ------------------------------------------------------------

@login_required
@require_POST
def evenement_inviter(request, pk):
    evenement = _evenement_modifiable(request, pk)
    form = InviterForm(request.POST)
    if form.is_valid():
        nouveaux = _inviter(evenement, form.invites(), request.user)
        messages.success(request, f"{len(nouveaux)} invitation{'s' if len(nouveaux) > 1 else ''} envoyée{'s' if len(nouveaux) > 1 else ''}.")
    return redirect(reverse("planning:evenement", args=[pk]) + "#invitations")


@login_required
@require_POST
def evenement_repondre(request, pk):
    evenement = _evenement_visible(request, pk)
    statut = request.POST.get("statut")
    if statut not in (Invitation.ACCEPTEE, Invitation.REFUSEE):
        raise Http404
    invitation, _ = Invitation.objects.get_or_create(evenement=evenement, membre=request.user)
    invitation.statut = statut
    invitation.commentaire = request.POST.get("commentaire", "")[:200]
    invitation.repondu_le = timezone.now()
    invitation.save()
    if evenement.createur_id and evenement.createur_id != request.user.pk:
        reponse = "accepte" if statut == Invitation.ACCEPTEE else "décline"
        services.notifier([evenement.createur_id], Notification.INVITATION,
                          f"{nom_membre(request.user)} {reponse} l'invitation : {evenement.titre}",
                          evenement.get_absolute_url())
    messages.success(request, "Réponse enregistrée.")
    return redirect(request.POST.get("retour") or reverse("planning:evenement", args=[pk]) + "#invitations")


@login_required
def invitations(request):
    maintenant = timezone.now()
    mes = (Invitation.objects.filter(membre=request.user, evenement__fin__gte=maintenant)
           .select_related("evenement").order_by("evenement__debut"))
    return render(request, "planning/invitations.html", {
        "en_attente": [i for i in mes if i.statut == Invitation.EN_ATTENTE],
        "repondues": [i for i in mes if i.statut != Invitation.EN_ATTENTE],
    })


# --- Créneaux ---------------------------------------------------------------

@login_required
def creneaux_decouper(request, pk):
    evenement = _evenement_modifiable(request, pk)
    form = DecouperForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        cibles = [evenement]
        if d["appliquer_serie"] and evenement.serie:
            cibles = list(evenement.occurrences_suivantes())
        total = 0
        with transaction.atomic():
            for cible in cibles:
                total += len(services.decouper(cible, d["duree"], d["besoin"], d["libelle"], d["remplacer"]))
        messages.success(request, f"{total} créneau{'x' if total > 1 else ''} créé{'s' if total > 1 else ''}.")
        return redirect(reverse("planning:evenement", args=[pk]) + "#creneaux")
    return render(request, "planning/creneaux_decouper.html", {"form": form, "evenement": evenement})


@login_required
def creneau_ajouter(request, pk):
    evenement = _evenement_modifiable(request, pk)
    form = CreneauForm(request.POST or None, initial={
        "debut": timezone.localtime(evenement.debut).replace(tzinfo=None),
        "fin": timezone.localtime(evenement.fin).replace(tzinfo=None), "besoin": 1,
    })
    if request.method == "POST" and form.is_valid():
        creneau = form.save(commit=False)
        creneau.evenement = evenement
        creneau.save()
        messages.success(request, "Créneau ajouté.")
        return redirect(reverse("planning:evenement", args=[pk]) + "#creneaux")
    return render(request, "planning/creneau_form.html", {"form": form, "evenement": evenement})


def _creneau_modifiable(request, pk):
    creneau = get_object_or_404(Creneau.objects.select_related("evenement"), pk=pk)
    _evenement_modifiable(request, creneau.evenement_id)
    return creneau


@login_required
def creneau_modifier(request, pk):
    creneau = _creneau_modifiable(request, pk)
    form = CreneauForm(request.POST or None, instance=creneau)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Créneau modifié.")
        return redirect(reverse("planning:evenement", args=[creneau.evenement_id]) + "#creneaux")
    return render(request, "planning/creneau_form.html", {"form": form, "evenement": creneau.evenement, "creneau": creneau})


@login_required
@require_POST
def creneau_supprimer(request, pk):
    creneau = _creneau_modifiable(request, pk)
    inscrits = list(creneau.inscriptions.filter(membre__isnull=False).values_list("membre", flat=True))
    evenement = creneau.evenement
    texte = f"Créneau supprimé : {evenement.titre}, {creneau}"
    creneau.delete()
    services.notifier(inscrits, Notification.EVENEMENT, texte, evenement.get_absolute_url(), exclure=request.user)
    messages.success(request, "Créneau supprimé.")
    return redirect(reverse("planning:evenement", args=[evenement.pk]) + "#creneaux")


def _retour(request, defaut):
    retour = request.POST.get("retour", "")
    return retour if retour.startswith("/planning/") else defaut


@login_required
@require_POST
def creneau_inscrire(request, pk):
    creneau = get_object_or_404(Creneau.objects.select_related("evenement"), pk=pk)
    evenement = _evenement_visible(request, creneau.evenement_id)
    membre = request.user
    nom = " ".join(request.POST.get("nom", "").split())[:100]
    if nom:
        # Un responsable (ou l'auteur de l'événement) note un bénévole sans compte
        if not evenement.peut_modifier(request.user):
            raise PermissionDenied
        membre = None
    elif request.POST.get("membre") and str(request.POST["membre"]) != str(request.user.pk):
        # Un responsable (ou l'auteur de l'événement) affecte quelqu'un
        if not evenement.peut_modifier(request.user):
            raise PermissionDenied
        membre = get_object_or_404(get_user_model(), pk=request.POST["membre"], is_active=True)
    defaut = reverse("planning:evenement", args=[evenement.pk]) + "#creneaux"
    if evenement.annule:
        messages.error(request, "Cet événement est annulé.")
        return redirect(_retour(request, defaut))
    with transaction.atomic():
        # Verrou : deux membres ne peuvent pas prendre la dernière place en même temps
        creneau = Creneau.objects.select_for_update().get(pk=creneau.pk)
        if creneau.inscriptions.count() >= creneau.besoin:
            messages.warning(request, "Ce créneau est déjà complet.")
            return redirect(_retour(request, defaut))
        try:
            with transaction.atomic():
                Inscription.objects.create(creneau=creneau, membre=membre, nom="" if membre else nom,
                                           ajoute_par=request.user)
        except IntegrityError:
            messages.info(request, "Déjà inscrit sur ce créneau.")
            return redirect(_retour(request, defaut))
    if membre is None:
        messages.success(request, f"{nom} est inscrit : {creneau}.")
    elif membre == request.user:
        messages.success(request, f"Merci ! Vous êtes inscrit : {evenement.titre}, {creneau}.")
    else:
        messages.success(request, f"{nom_membre(membre)} est inscrit : {creneau}.")
        services.notifier([membre], Notification.EVENEMENT,
                          f"{nom_membre(request.user)} vous a inscrit : {evenement.titre}, {creneau}",
                          evenement.get_absolute_url())
    return redirect(_retour(request, defaut))


@login_required
@require_POST
def creneau_desinscrire(request, pk):
    creneau = get_object_or_404(Creneau.objects.select_related("evenement"), pk=pk)
    evenement = _evenement_visible(request, creneau.evenement_id)
    defaut = reverse("planning:evenement", args=[evenement.pk]) + "#creneaux"
    if request.POST.get("inscription"):
        # Nom libre (bénévole sans compte) : réservé aux organisateurs
        if not evenement.peut_modifier(request.user):
            raise PermissionDenied
        creneau.inscriptions.filter(pk=request.POST["inscription"], membre__isnull=True).delete()
        messages.success(request, "Nom retiré du créneau.")
        return redirect(_retour(request, defaut))
    membre_id = request.POST.get("membre") or request.user.pk
    if str(membre_id) != str(request.user.pk) and not evenement.peut_modifier(request.user):
        raise PermissionDenied
    creneau.inscriptions.filter(membre_id=membre_id).delete()
    if str(membre_id) == str(request.user.pk) and evenement.createur_id:
        services.notifier([evenement.createur_id], Notification.EVENEMENT,
                          f"{nom_membre(request.user)} s'est désinscrit : {evenement.titre}, {creneau}",
                          evenement.get_absolute_url(), exclure=request.user)
    messages.success(request, "Désinscription enregistrée.")
    return redirect(_retour(request, defaut))


# --- Couverture des besoins (« bouche-trous ») ------------------------------

PERIODES_COUVERTURE = {"7": 7, "30": 30, "90": 90}


@login_required
def couverture(request):
    periode = request.GET.get("jours", "30")
    nb_jours = PERIODES_COUVERTURE.get(periode, 30)
    responsable = est_responsable(request.user)
    tout_voir = responsable and request.GET.get("tout") == "1"
    maintenant = timezone.now()
    fin = maintenant + timedelta(days=nb_jours)
    visibles = Evenement.objects.visibles_par(request.user).filter(annule=False).values("pk")
    creneaux = (Creneau.objects.avec_effectif()
                .filter(evenement__in=visibles, fin__gt=maintenant, debut__lt=fin)
                .select_related("evenement").prefetch_related("inscriptions__membre"))
    if not tout_voir:
        creneaux = creneaux.filter(nb_inscrits__lt=F("besoin"))
    par_evenement, stats = {}, {"creneaux": 0, "places": 0, "manque": 0, "vides": 0, "urgents": 0}
    for c in creneaux:
        _repartir_inscrits(c, request.user)
        c.manque = max(0, c.besoin - c.nb_inscrits)
        c.taux = round(min(c.nb_inscrits, c.besoin) * 100 / c.besoin) if c.besoin else 100
        c.urgent = c.manque and c.est_urgent()
        par_evenement.setdefault(c.evenement, []).append(c)
        stats["creneaux"] += 1
        stats["places"] += c.besoin
        stats["manque"] += c.manque
        stats["vides"] += int(c.nb_inscrits == 0)
        stats["urgents"] += int(bool(c.urgent))
    jours_concernes = {timezone.localtime(c.debut).date() for liste_c in par_evenement.values() for c in liste_c if c.manque}
    disponibles = defaultdict(list)
    if responsable and jours_concernes:
        for d in Disponibilite.objects.filter(date__in=jours_concernes).select_related("membre"):
            disponibles[d.date].append(d)
    return render(request, "planning/couverture.html", {
        "evenements": [{"evenement": e, "creneaux": liste_c, "jour": timezone.localtime(e.debut).date(),
                        "disponibles": disponibles.get(timezone.localtime(liste_c[0].debut).date(), [])}
                       for e, liste_c in par_evenement.items()],
        "stats": stats, "periode": periode, "periodes": PERIODES_COUVERTURE, "tout_voir": tout_voir,
        "est_responsable": responsable, "membres": services.membres_actifs() if responsable else [],
    })


# --- Disponibilités ---------------------------------------------------------

@login_required
def disponibilites(request):
    form = DisponibiliteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        dispo = form.save(commit=False)
        dispo.membre = request.user
        dispo.save()
        messages.success(request, f"Disponibilité ajoutée : {dispo.date:%d/%m/%Y}, {dispo.plage()}.")
        return redirect("planning:disponibilites")
    aujourdhui = timezone.localdate()
    contexte = {
        "form": form,
        "mes_disponibilites": Disponibilite.objects.filter(membre=request.user, date__gte=aujourdhui),
        "est_responsable": est_responsable(request.user),
    }
    if contexte["est_responsable"]:
        par_date = defaultdict(list)
        for d in Disponibilite.objects.filter(date__gte=aujourdhui, date__lte=aujourdhui + timedelta(days=60)).select_related("membre"):
            par_date[d.date].append(d)
        contexte["toutes"] = [{"date": d, "nom": JOURS[d.weekday()], "disponibilites": par_date[d]} for d in sorted(par_date)]
    return render(request, "planning/disponibilites.html", contexte)


@login_required
@require_POST
def disponibilite_supprimer(request, pk):
    get_object_or_404(Disponibilite, pk=pk, membre=request.user).delete()
    messages.success(request, "Disponibilité retirée.")
    return redirect("planning:disponibilites")


# --- Tableau des tâches -----------------------------------------------------

def _plages(formset):
    """Plages (début, fin) saisies ; une fin avant le début passe minuit."""
    plages = []
    for form in formset:
        d = form.cleaned_data
        if d and d.get("heure_debut"):
            debut = timezone.make_aware(datetime.combine(d["date"], d["heure_debut"]))
            fin = timezone.make_aware(datetime.combine(d["date"], d["heure_fin"]))
            if fin <= debut:
                fin += timedelta(days=1)
            plages.append((debut, fin))
    return plages


def _creer_creneaux(evenement, plages, libelle, besoin, duree=None, decalage=timedelta(0)):
    nouveaux = []
    for debut, fin in plages:
        debut, fin = debut + decalage, fin + decalage
        pas = timedelta(minutes=duree) if duree else fin - debut
        while debut < fin:
            suivant = min(debut + pas, fin)
            nouveaux.append(Creneau(evenement=evenement, libelle=libelle, besoin=besoin, debut=debut, fin=suivant))
            debut = suivant
    return Creneau.objects.bulk_create(nouveaux)


def _creneaux_de_la_tache(evenement, request):
    libelle = request.GET.get("tache", request.POST.get("tache_initiale", ""))
    creneaux = evenement.creneaux.filter(libelle=libelle)
    if not creneaux.exists():
        raise Http404
    return libelle, creneaux


def _formulaire_tache(request, evenement, libelle=None):
    """Ajout (libelle None) ou modification d'une tâche et de ses plages."""
    creneaux = evenement.creneaux.filter(libelle=libelle) if libelle is not None else Creneau.objects.none()
    debut_local, fin_local = timezone.localtime(evenement.debut), timezone.localtime(evenement.fin)
    initial = {"libelle": libelle, "besoin": creneaux.first().besoin} if libelle is not None else {}
    # Lignes de plages : le jour de l'événement est pré-rempli, il reste les heures
    lignes_vides = [{"date": debut_local.date()}] * 4
    plage_initiale = lignes_vides if libelle is not None else [{
        "date": debut_local.date(), "heure_debut": debut_local.time(), "heure_fin": fin_local.time(),
    }] + lignes_vides
    form = TacheForm(request.POST or None, initial=initial)
    plages_form = PlagesFormSet(request.POST or None, prefix="plages", initial=plage_initiale)
    erreur = ""
    if request.method == "POST" and form.is_valid() and plages_form.is_valid():
        d = form.cleaned_data
        plages = _plages(plages_form)
        nouveau_libelle = d["libelle"].strip()
        if libelle is None and not plages:
            erreur = "Indiquez au moins une plage horaire."
        elif nouveau_libelle != (libelle or "") and evenement.creneaux.filter(libelle=nouveau_libelle).exists():
            erreur = f"La tâche « {nouveau_libelle} » existe déjà : choisissez un autre nom."
        else:
            with transaction.atomic():
                if libelle is not None:
                    creneaux.update(libelle=nouveau_libelle, besoin=d["besoin"])
                crees = _creer_creneaux(evenement, plages, nouveau_libelle, d["besoin"], d.get("duree"))
                if d.get("appliquer_serie") and evenement.serie and plages:
                    for occurrence in evenement.occurrences_suivantes().exclude(pk=evenement.pk):
                        _creer_creneaux(occurrence, plages, nouveau_libelle, d["besoin"], d.get("duree"),
                                        decalage=occurrence.debut - evenement.debut)
            if libelle is None:
                messages.success(request, f"Tâche « {nouveau_libelle} » ajoutée ({len(crees)} case{'s' if len(crees) > 1 else ''}).")
            else:
                messages.success(request, f"Tâche « {nouveau_libelle} » modifiée.")
            if "encore" in request.POST:
                return redirect("planning:tache_ajouter", pk=evenement.pk)
            return redirect(reverse("planning:evenement", args=[evenement.pk]) + "#creneaux")
    return render(request, "planning/tache_form.html", {
        "form": form, "plages_form": plages_form, "erreur": erreur, "evenement": evenement,
        "libelle": libelle, "nb_cases": creneaux.count(),
    })


@login_required
def tache_ajouter(request, pk):
    return _formulaire_tache(request, _evenement_modifiable(request, pk))


@login_required
def tache_modifier(request, pk):
    evenement = _evenement_modifiable(request, pk)
    libelle, _ = _creneaux_de_la_tache(evenement, request)
    return _formulaire_tache(request, evenement, libelle)


@login_required
@require_POST
def tache_supprimer(request, pk):
    evenement = _evenement_modifiable(request, pk)
    libelle, creneaux = _creneaux_de_la_tache(evenement, request)
    inscrits = set(Inscription.objects.filter(creneau__in=creneaux, membre__isnull=False)
                   .values_list("membre", flat=True))
    creneaux.delete()
    nom = libelle or "Bénévoles"
    services.notifier(inscrits, Notification.EVENEMENT, f"Tâche supprimée : {nom}, {evenement.titre}",
                      evenement.get_absolute_url(), exclure=request.user)
    messages.success(request, f"Tâche « {nom} » supprimée.")
    return redirect(reverse("planning:evenement", args=[evenement.pk]) + "#creneaux")
