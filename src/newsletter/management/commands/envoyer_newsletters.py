"""
Envoie les newsletters en attente, par lots.

À planifier toutes les 5 minutes (cPanel > Tâches Cron) :

    */5 * * * * cd ~/concorde/src && DJANGO_SETTINGS_MODULE=concorde_site.settings.production \
        ~/virtualenv/concorde/src/3.11/bin/python manage.py envoyer_newsletters >> ~/concorde/src/newsletter-cron.log 2>&1

Sans envoi en cours, la commande ne fait rien et se termine aussitôt.
"""
import fcntl
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from newsletter.envoi import traiter_lot


class Command(BaseCommand):
    help = "Envoie un lot de newsletters en attente (à lancer régulièrement par une tâche cron)."

    def add_arguments(self, parser):
        parser.add_argument("--lot", type=int, default=None, help="Nombre de messages (défaut : NEWSLETTER_LOT_TAILLE).")
        parser.add_argument("--pause", type=float, default=None, help="Pause entre deux messages, en secondes.")
        parser.add_argument("--silencieux", action="store_true", help="N'affiche que les erreurs.")

    def handle(self, *args, **options):
        # Verrou : si le passage précédent n'est pas fini, on n'en lance pas un second.
        dossier = os.path.join(settings.BASE_DIR, "tmp")
        os.makedirs(dossier, exist_ok=True)
        with open(os.path.join(dossier, "newsletter-envoi.lock"), "w") as verrou:
            try:
                fcntl.flock(verrou, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                if not options["silencieux"]:
                    self.stdout.write("Un envoi est déjà en cours : rien à faire.")
                return

            journal = (lambda texte: None) if options["silencieux"] else self.stdout.write
            nb = traiter_lot(taille=options["lot"], pause=options["pause"], journal=journal)
            if nb and not options["silencieux"]:
                self.stdout.write(self.style.SUCCESS(f"{nb} message(s) envoyé(s)."))
