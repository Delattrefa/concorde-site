"""
Tâches régulières du planning, à planifier toutes les 5 minutes (cPanel >
Tâches Cron), comme l'envoi des newsletters :

    */5 * * * * cd ~/concorde/src && DJANGO_SETTINGS_MODULE=concorde_site.settings.production \\
        ~/virtualenv/concorde/src/3.11/bin/python manage.py planning_taches >> ~/concorde/src/planning-cron.log 2>&1

1. Alerte « bénévoles manquants » : une seule fois par événement, quand
   un de ses créneaux incomplets commence dans moins de
   PLANNING_URGENCE_HEURES (2 jours) ; tous les membres sont prévenus.
2. E-mails : les notifications en attente partent groupées, un seul
   e-mail par membre et par passage.
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from planning import services
from planning.models import Creneau, Notification

logger = logging.getLogger("planning")


def alerter_creneaux_urgents():
    """Une seule alerte par événement, même s'il a plusieurs créneaux
    incomplets : ses créneaux sont tous marqués « alerte envoyée »."""
    maintenant = timezone.now()
    urgents = (
        Creneau.objects.a_combler()
        .filter(alerte_envoyee=False, debut__gt=maintenant,
                debut__lte=maintenant + timedelta(hours=settings.PLANNING_URGENCE_HEURES))
        .select_related("evenement")
    )
    par_evenement = defaultdict(list)
    for creneau in urgents:
        par_evenement[creneau.evenement].append(creneau)
    for evenement, creneaux in par_evenement.items():
        manque = sum(c.besoin - c.nb_inscrits for c in creneaux)
        if evenement.reserve_aux_invites:
            destinataires = evenement.participants()
        else:
            destinataires = services.membres_actifs().values_list("pk", flat=True)
        debut = timezone.localtime(min(c.debut for c in creneaux))
        services.notifier(
            destinataires, Notification.URGENCE,
            f"Il manque {manque} bénévole{'s' if manque > 1 else ''} pour {evenement.titre} ({debut:%d/%m à %H:%M})",
            evenement.get_absolute_url() + "#creneaux",
        )
    Creneau.objects.filter(evenement__in=list(par_evenement)).update(alerte_envoyee=True)
    return len(par_evenement)


def envoyer_emails():
    a_envoyer = list(
        Notification.objects.filter(a_envoyer=True, envoyee_le=None)
        .select_related("destinataire").order_by("cree_le")[:2000]
    )
    par_membre = defaultdict(list)
    for n in a_envoyer:
        par_membre[n.destinataire].append(n)
    base = (getattr(settings, "WAGTAILADMIN_BASE_URL", "") or "").rstrip("/")
    envoyes, connexion = 0, get_connection()
    for membre, liste in par_membre.items():
        if membre.email and membre.is_active:
            contexte = {"membre": membre, "notifications": liste, "base": base}
            sujet = (f"La Concorde — Planning : {liste[0].texte}" if len(liste) == 1
                     else f"La Concorde — Planning : {len(liste)} nouveautés")
            message = EmailMessage(
                sujet[:150], render_to_string("planning/emails/notifications.txt", contexte),
                to=[membre.email], connection=connexion,
            )
            try:
                message.send()
                envoyes += 1
            except Exception:
                logger.exception("Planning : e-mail non envoyé à %s", membre.email)
                continue
        Notification.objects.filter(pk__in=[n.pk for n in liste]).update(envoyee_le=timezone.now())
    return envoyes


class Command(BaseCommand):
    help = "Alertes des créneaux urgents et envoi groupé des notifications du planning par e-mail."

    def handle(self, *args, **options):
        urgents = alerter_creneaux_urgents()
        envoyes = envoyer_emails()
        if urgents or envoyes:
            self.stdout.write(f"{timezone.localtime():%d/%m/%Y %H:%M} : {urgents} créneau(x) urgent(s) signalé(s), "
                              f"{envoyes} e-mail(s) envoyé(s).")
