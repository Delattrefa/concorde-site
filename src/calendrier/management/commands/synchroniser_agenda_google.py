"""
Remet l'agenda Google partagé en accord avec le calendrier du site.

- recopie toutes les activités et les locations validées (création ou mise
  à jour : un événement modifié à la main dans Google est remis en état) ;
- retire les locations qui ne sont plus validées ;
- supprime les événements créés par le site dont l'activité ou la
  location n'existe plus (suppression faite pendant une panne de Google).
  Les événements ajoutés à la main dans Google ne sont jamais touchés.

À lancer une fois à la mise en place, puis chaque nuit (tâche cron) pour
rattraper les échecs éventuels.

Usage : python manage.py synchroniser_agenda_google [--depuis AAAA-MM-JJ]
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from calendrier import google_agenda
from calendrier.models import Activite, Reservation


class Command(BaseCommand):
    help = "Recopie les activités et les locations validées dans l'agenda Google partagé."

    def add_arguments(self, parser):
        parser.add_argument(
            "--depuis", type=date.fromisoformat,
            help="Ne traiter que ce qui se termine à partir de cette date (par défaut : tout).",
        )

    def handle(self, *args, depuis=None, **options):
        if not google_agenda.actif():
            raise CommandError("GOOGLE_AGENDA_ID et GOOGLE_AGENDA_CLE ne sont pas renseignés dans le .env.")

        objets = []
        for modele in (Activite, Reservation):
            requete = modele.objects.all()
            if depuis:
                requete = requete.filter(date_fin__gte=depuis)
            objets += list(requete)

        echecs = sum(not google_agenda.synchroniser(objet) for objet in objets)

        # Événements dont l'objet n'existe plus sur le site
        attendus = {
            objet.google_event_id for modele in (Activite, Reservation)
            for objet in modele.objects.exclude(google_event_id="")
        }
        try:
            orphelins = [eid for eid in google_agenda.evenements_du_site() if eid not in attendus]
        except Exception as erreur:
            raise CommandError(f"Lecture de l'agenda Google impossible : {erreur}")
        echecs += sum(not google_agenda.supprimer(eid) for eid in orphelins)

        self.stdout.write(
            f"{len(objets)} élément(s) vérifié(s), {len(orphelins)} événement(s) orphelin(s) supprimé(s)."
        )
        if echecs:
            raise CommandError(f"{echecs} échec(s) : voir le journal des erreurs (django-erreurs.log).")
        self.stdout.write(self.style.SUCCESS("Agenda Google à jour."))
