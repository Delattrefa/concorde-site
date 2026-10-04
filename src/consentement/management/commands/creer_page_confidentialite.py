"""
Crée la page « Politique de confidentialité » (type Info) sous la page
d'accueil et la relie au bandeau de cookies.

    python manage.py creer_page_confidentialite             # brouillon à relire
    python manage.py creer_page_confidentialite --publier   # publiée directement

La page est créée en brouillon par défaut : relisez-la et publiez-la depuis
l'admin Wagtail. Si elle existe déjà, rien n'est modifié.
"""
from django.core.management.base import BaseCommand, CommandError

from wagtail.models import Site
from wagtail.rich_text import RichText

from consentement.models import ConsentementCookies
from consentement.politique import CONTENU
from info.models import InfoPage

SLUG = "politique-de-confidentialite"


def _blocs():
    blocs = []
    for type_bloc, valeur in CONTENU:
        if type_bloc == "heading":
            blocs.append(("heading", valeur))
        elif type_bloc == "paragraph":
            blocs.append(("paragraph", RichText(valeur)))
        elif type_bloc == "callout":
            titre, texte = valeur
            blocs.append(("callout", {"title": titre, "text": RichText(texte)}))
    return blocs


class Command(BaseCommand):
    help = "Crée la page « Politique de confidentialité » et la relie au bandeau de cookies."

    def add_arguments(self, parser):
        parser.add_argument("--publier", action="store_true", help="Publier la page immédiatement.")

    def handle(self, *args, **options):
        site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
        if site is None:
            raise CommandError("Aucun site Wagtail n'est configuré.")
        accueil = site.root_page.specific

        page = InfoPage.objects.child_of(accueil).filter(slug=SLUG).first()
        if page:
            self.stdout.write(self.style.WARNING(
                f"La page existe déjà (« {page.title} ») : elle n'a pas été modifiée."
            ))
        else:
            page = InfoPage(
                title="Politique de confidentialité",
                slug=SLUG,
                body=_blocs(),
                show_in_menus=False,
                live=False,
                search_description=(
                    "Comment La Concorde asbl collecte, utilise et protège vos données "
                    "personnelles, et comment exercer vos droits."
                ),
            )
            accueil.add_child(instance=page)
            revision = page.save_revision()
            if options["publier"]:
                revision.publish()
                self.stdout.write(self.style.SUCCESS("Page créée et publiée."))
            else:
                self.stdout.write(self.style.SUCCESS(
                    "Page créée en brouillon : relisez-la et publiez-la depuis l'admin Wagtail."
                ))

        reglages = ConsentementCookies.for_site(site)
        if reglages.page_politique_id != page.pk:
            reglages.page_politique = page
            reglages.save()
            self.stdout.write("Page reliée au bandeau de cookies (Paramètres > Consentement aux cookies).")
