"""
Moteur d'envoi de la newsletter, par lots.

o2switch n'autorise ni Celery ni Redis sur l'hébergement mutualisé et son
serveur SMTP est prévu pour des envois courants, pas des campagnes massives.
L'envoi est donc découpé :

1. lancer_envoi() fige la liste des destinataires (une Livraison chacun).
2. traiter_lot() envoie un petit lot sur une seule connexion SMTP, avec une
   pause entre deux messages et un plafond horaire. Il est appelé toutes les
   5 minutes par la tâche cron `python manage.py envoyer_newsletters`, et
   peut aussi être déclenché depuis l'admin.

Réglages (settings) :
    NEWSLETTER_LOT_TAILLE          messages par lot (défaut 15)
    NEWSLETTER_PAUSE_SECONDES      pause entre deux messages (défaut 2)
    NEWSLETTER_MAX_PAR_HEURE       plafond sur une heure glissante (défaut 150)
    NEWSLETTER_TENTATIVES_MAX      essais avant d'abandonner une adresse (défaut 3)
"""
import logging
import smtplib
import time
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.utils import timezone

from .models import Abonne, Envoi, Livraison, Newsletter
from .rendu import personnaliser, rendre_newsletter

logger = logging.getLogger("newsletter")


def _reglage(nom, defaut):
    return getattr(settings, nom, defaut)


def destinataires_possibles(newsletter):
    """Abonnés actifs qui n'ont pas encore reçu cette newsletter."""
    deja_recus = Livraison.objects.filter(
        envoi__newsletter=newsletter, statut=Livraison.STATUT_ENVOYE
    ).values_list("email", flat=True)
    return Abonne.objects.filter(statut=Abonne.STATUT_ACTIF).exclude(email__in=deja_recus)


def envoi_actif(newsletter):
    return newsletter.envois.filter(statut=Envoi.STATUT_EN_COURS).first()


@transaction.atomic
def lancer_envoi(newsletter, utilisateur=None):
    """Crée l'envoi et sa file de destinataires. Renvoie l'Envoi."""
    newsletter = Newsletter.objects.select_for_update().get(pk=newsletter.pk)
    existant = envoi_actif(newsletter)
    if existant:
        return existant

    envoi = Envoi.objects.create(newsletter=newsletter, lance_par=utilisateur)
    Livraison.objects.bulk_create(
        [Livraison(envoi=envoi, abonne=a, email=a.email) for a in destinataires_possibles(newsletter)],
        batch_size=500,
    )
    newsletter.statut = Newsletter.STATUT_EN_COURS
    newsletter.save(update_fields=["statut"])
    _terminer_si_fini(envoi)
    return envoi


def annuler_envoi(envoi):
    envoi.livraisons.filter(statut=Livraison.STATUT_A_ENVOYER).update(
        statut=Livraison.STATUT_IGNORE, erreur="Envoi annulé"
    )
    envoi.statut = Envoi.STATUT_ANNULE
    envoi.date_fin = timezone.now()
    envoi.save(update_fields=["statut", "date_fin"])
    _mettre_a_jour_newsletter(envoi.newsletter)


def _mettre_a_jour_newsletter(newsletter):
    if newsletter.envois.filter(statut=Envoi.STATUT_EN_COURS).exists():
        statut = Newsletter.STATUT_EN_COURS
    elif Livraison.objects.filter(envoi__newsletter=newsletter, statut=Livraison.STATUT_ENVOYE).exists():
        statut = Newsletter.STATUT_ENVOYEE
    else:
        statut = Newsletter.STATUT_BROUILLON
    champs = ["statut"]
    newsletter.statut = statut
    if statut == Newsletter.STATUT_ENVOYEE and not newsletter.date_envoi:
        newsletter.date_envoi = timezone.now()
        champs.append("date_envoi")
    newsletter.save(update_fields=champs)


def _terminer_si_fini(envoi):
    if not envoi.livraisons.filter(statut=Livraison.STATUT_A_ENVOYER).exists():
        envoi.statut = Envoi.STATUT_TERMINE
        envoi.date_fin = timezone.now()
        envoi.save(update_fields=["statut", "date_fin"])
        _mettre_a_jour_newsletter(envoi.newsletter)
        logger.info("Envoi terminé : %s", envoi)


def construire_message(newsletter, contenu_html, contenu_texte, email, prenom="", url_desinscription="", connection=None):
    """Message personnalisé pour un destinataire, avec les en-têtes de
    désinscription en un clic (exigés par Gmail et Yahoo pour les envois groupés)."""
    expediteur = _reglage("NEWSLETTER_FROM_EMAIL", None) or settings.DEFAULT_FROM_EMAIL
    entetes = {}
    if url_desinscription.startswith("http"):
        entetes["List-Unsubscribe"] = f"<{url_desinscription}>"
        entetes["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    reponse = _reglage("NEWSLETTER_REPLY_TO", "")
    message = EmailMultiAlternatives(
        subject=newsletter.objet,
        body=personnaliser(contenu_texte, prenom, url_desinscription),
        from_email=expediteur,
        to=[email],
        reply_to=[reponse] if reponse else None,
        headers=entetes,
        connection=connection,
    )
    message.attach_alternative(personnaliser(contenu_html, prenom, url_desinscription), "text/html")
    return message


def envoyer_test(newsletter, adresses):
    """Envoie immédiatement la newsletter à quelques adresses de test
    (objet préfixé « [TEST] »). Renvoie le nombre de messages envoyés."""
    contenu_html, contenu_texte = rendre_newsletter(newsletter)
    connexion = get_connection()
    messages = []
    for adresse in adresses:
        message = construire_message(newsletter, contenu_html, contenu_texte, adresse, "", "#", connexion)
        message.subject = f"[TEST] {newsletter.objet}"
        messages.append(message)
    return connexion.send_messages(messages) or 0


def envois_derniere_heure():
    return Livraison.objects.filter(
        statut=Livraison.STATUT_ENVOYE, date_envoi__gte=timezone.now() - timedelta(hours=1)
    ).count()


def traiter_lot(taille=None, pause=None, journal=None):
    """Envoie au plus `taille` messages en attente (tous envois confondus,
    du plus ancien envoi au plus récent). Renvoie le nombre de messages
    envoyés. `journal` : fonction appelée avec des lignes de suivi."""
    journal = journal or (lambda texte: logger.info(texte))
    taille = taille if taille is not None else _reglage("NEWSLETTER_LOT_TAILLE", 15)
    pause = pause if pause is not None else _reglage("NEWSLETTER_PAUSE_SECONDES", 2)
    max_heure = _reglage("NEWSLETTER_MAX_PAR_HEURE", 150)
    tentatives_max = _reglage("NEWSLETTER_TENTATIVES_MAX", 3)

    disponibles = max(0, max_heure - envois_derniere_heure())
    taille = min(taille, disponibles)
    if taille <= 0:
        journal(f"Plafond horaire atteint ({max_heure} messages) : reprise au prochain passage.")
        return 0

    livraisons = list(
        Livraison.objects.filter(statut=Livraison.STATUT_A_ENVOYER, envoi__statut=Envoi.STATUT_EN_COURS)
        .select_related("envoi__newsletter", "abonne")
        .order_by("envoi__date_lancement", "pk")[:taille]
    )
    if not livraisons:
        return 0

    rendus = {}          # un rendu HTML par newsletter, réutilisé pour tout le lot
    envois_touches = {}
    nb_envoyes = 0
    connexion = get_connection()
    try:
        connexion.open()
        for index, livraison in enumerate(livraisons):
            envoi = livraison.envoi
            envois_touches[envoi.pk] = envoi
            abonne = livraison.abonne

            # Désinscrit entre-temps (ou supprimé) : on n'envoie pas.
            if abonne is None or abonne.statut != Abonne.STATUT_ACTIF:
                livraison.statut = Livraison.STATUT_IGNORE
                livraison.erreur = "Désinscrit avant l'envoi"
                livraison.save(update_fields=["statut", "erreur"])
                continue

            if envoi.newsletter_id not in rendus:
                rendus[envoi.newsletter_id] = rendre_newsletter(envoi.newsletter)
            contenu_html, contenu_texte = rendus[envoi.newsletter_id]

            message = construire_message(
                envoi.newsletter, contenu_html, contenu_texte, abonne.email,
                abonne.prenom, abonne.url_desinscription, connexion,
            )
            livraison.tentatives += 1
            try:
                message.send()
            except smtplib.SMTPDataError as exc:
                if exc.smtp_code < 500:
                    # Refus temporaire (4xx, souvent un quota) : on arrête le
                    # lot et on réessaiera au prochain passage.
                    livraison.tentatives -= 1
                    envoi.derniere_erreur = f"{timezone.now():%d/%m/%Y %H:%M} — refus temporaire : {exc}"[:2000]
                    envoi.save(update_fields=["derniere_erreur"])
                    journal(f"Refus temporaire du serveur, lot interrompu : {exc}")
                    break
                livraison.erreur = str(exc)[:255]
                if livraison.tentatives >= tentatives_max:
                    livraison.statut = Livraison.STATUT_ECHEC
                livraison.save(update_fields=["statut", "erreur", "tentatives"])
                journal(f"  échec {abonne.email} : {livraison.erreur}")
                continue
            except smtplib.SMTPRecipientsRefused as exc:
                # Problème propre à cette adresse : on la marque, on continue.
                livraison.erreur = str(exc)[:255]
                if livraison.tentatives >= tentatives_max:
                    livraison.statut = Livraison.STATUT_ECHEC
                livraison.save(update_fields=["statut", "erreur", "tentatives"])
                journal(f"  échec {abonne.email} : {livraison.erreur}")
                continue
            except (smtplib.SMTPException, OSError) as exc:
                # Problème de serveur (authentification, connexion, quota) :
                # on arrête le lot, la livraison reste à envoyer.
                livraison.tentatives -= 1
                envoi.derniere_erreur = f"{timezone.now():%d/%m/%Y %H:%M} — {exc}"[:2000]
                envoi.save(update_fields=["derniere_erreur"])
                journal(f"Erreur du serveur SMTP, lot interrompu : {exc}")
                break

            livraison.statut = Livraison.STATUT_ENVOYE
            livraison.erreur = ""
            livraison.date_envoi = timezone.now()
            livraison.save(update_fields=["statut", "erreur", "tentatives", "date_envoi"])
            nb_envoyes += 1
            journal(f"  envoyé à {abonne.email}")

            if pause and index < len(livraisons) - 1:
                time.sleep(pause)
    finally:
        connexion.close()
        for envoi in envois_touches.values():
            _terminer_si_fini(envoi)

    return nb_envoyes
