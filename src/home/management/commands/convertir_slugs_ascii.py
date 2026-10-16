"""
Retire les accents des slugs des pages existantes.

Les serveurs d'o2switch ne servent pas les URL accentuées : « médias »
devient « medias », et les adresses des sous-pages suivent. Les révisions
sont corrigées aussi, pour qu'un brouillon publié plus tard ne remette
pas l'ancien slug. Sans effet si tous les slugs sont déjà en ASCII.

Usage : python manage.py convertir_slugs_ascii [--dry-run]
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.models import Page

from home.slugs import slug_ascii


class Command(BaseCommand):
    help = "Retire les accents des slugs des pages Wagtail."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les changements sans les enregistrer.",
        )

    def handle(self, *args, dry_run=False, **options):
        # Parents d'abord : leurs sous-pages sont relues après leur mise à jour
        ids = [
            page.id
            for page in Page.objects.order_by("depth", "path").only("id", "slug")
            if not page.slug.isascii()
        ]
        if not ids:
            self.stdout.write("Tous les slugs sont déjà sans accents.")
            return

        with transaction.atomic():
            for page_id in ids:
                page = Page.objects.get(id=page_id).specific
                ancien = page.slug
                nouveau = self._slug_libre(page, slug_ascii(ancien) or "page")
                self.stdout.write(f"{page.url_path} : {ancien} → {nouveau}")
                if dry_run:
                    continue

                page.slug = nouveau
                page.save(clean=False)
                for revision in page.revisions.all():
                    if revision.content.get("slug") == ancien:
                        revision.content["slug"] = nouveau
                        revision.save(update_fields=["content"])

        if dry_run:
            self.stdout.write("Simulation : rien n'a été enregistré.")
        else:
            self.stdout.write(self.style.SUCCESS(f"{len(ids)} slug(s) converti(s)."))

    def _slug_libre(self, page, slug):
        """Ajoute -2, -3… si une page sœur porte déjà ce slug."""
        parent = page.get_parent()
        candidat, numero = slug, 1
        while not Page._slug_is_available(candidat, parent, page):
            numero += 1
            candidat = f"{slug}-{numero}"
        return candidat
