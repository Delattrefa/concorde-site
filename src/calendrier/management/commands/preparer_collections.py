"""
Vérifie la médiathèque Wagtail au déploiement : collections « Calendrier »
et « Calendrier › Signature » présentes (créées sinon), signatures
réservées aux super-utilisateurs et fichiers de signature à l'abri.
Voir calendrier/collections.py. Sans effet si tout est déjà en ordre.

Usage : python manage.py preparer_collections
"""
from django.core.management.base import BaseCommand

from calendrier.collections import preparer_collections


class Command(BaseCommand):
    help = "Crée les collections Calendrier › Signature et protège les signatures."

    def handle(self, *args, **options):
        rapport = preparer_collections()
        for ligne in rapport:
            self.stdout.write(f"  {ligne}")
        self.stdout.write(self.style.SUCCESS(
            "Collections Calendrier › Signature en ordre." if rapport else "Collections Calendrier › Signature déjà en ordre."
        ))
