"""
E-mail aux comptes « Statut équipe » à chaque nouvelle demande de
réservation de salle déposée sur le site.

Un e-mail par destinataire (les adresses de l'équipe ne sont pas montrées
aux autres). « Répondre » écrit directement au demandeur. Un échec d'envoi
est noté dans le journal sans bloquer la demande du visiteur.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage, get_connection
from django.template.loader import render_to_string
from django.urls import reverse

from .models import demandes_en_attente_sur

logger = logging.getLogger(__name__)


def destinataires_equipe():
    return list(
        get_user_model().objects.filter(is_active=True, is_staff=True)
        .exclude(email="").values_list("email", flat=True).distinct()
    )


def signaler_nouvelle_demande(reservation):
    destinataires = destinataires_equipe()
    if not destinataires:
        return 0
    base = settings.WAGTAILADMIN_BASE_URL.rstrip("/")
    contexte = {
        "reservation": reservation,
        "lien_fiche": base + reverse("calendrier:reservation_detail", args=[reservation.pk]),
        "lien_liste": base + reverse("calendrier:reservation_liste"),
        "autres_demandes": demandes_en_attente_sur(
            reservation.date_debut, reservation.date_fin, exclure=reservation.pk
        ).count(),
    }
    sujet = f"Nouvelle demande de réservation de la salle — {reservation.nom_court}, {reservation.periode_texte}"
    corps = render_to_string("calendrier/emails/nouvelle_demande.txt", contexte)
    messages = [
        EmailMessage(sujet, corps, to=[adresse], reply_to=[reservation.email])
        for adresse in destinataires
    ]
    try:
        return get_connection().send_messages(messages) or 0
    except Exception:
        logger.exception("Demande de réservation %s : e-mail à l'équipe non envoyé", reservation.pk)
        return 0
