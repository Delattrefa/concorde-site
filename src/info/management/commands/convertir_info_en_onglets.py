"""
Transforme la page Info en page à onglets, une seule fois.

Chaque lien vers une page libre devient un onglet qui reprend le contenu de
cette page (logo et titres, sections, galerie). Chaque titre suivi de contenu
devient aussi un onglet ; un titre seul reste en introduction au-dessus.

- Sans effet dès que la page a un onglet : un lien vers une page libre ajouté
  plus tard reste un lien.
- Rien n'est supprimé : les pages libres restent en ligne et s'effacent à la
  main, après vérification. Une redirection vers l'onglet est préparée pour
  chacune ; elle ne sert qu'une fois la page supprimée.
- Une page libre non publiée ou à accès restreint reste un lien : l'onglet
  rendrait son contenu public.

Usage : python manage.py convertir_info_en_onglets [--dry-run]
"""
import json
import re
import uuid

from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.contrib.redirects.models import Redirect
from wagtail.models import ReferenceIndex

from info.models import MAX_ONGLETS, InfoOnglet, InfoPage, ancres_onglets
from page_libre.models import PageLibre

SLUG_INFO = "info"
LONGUEUR_TITRE = InfoOnglet._meta.get_field("titre").max_length
RE_SEPARATEUR = re.compile(r"^[\W_]*$")


def bloc(type_bloc, valeur):
    return {"type": type_bloc, "value": valeur, "id": str(uuid.uuid4())}


def section_en_bloc(section):
    liens = list(section.liens.raw_data)
    if section.type_section == section.TYPE_COLONNES:
        return bloc("colonnes", {
            "titre_colonnes": section.titre_colonnes,
            "image_fond_colonnes": section.image_fond_colonnes_id,
            "taille_image": section.taille_image,
            "colonnes": [
                {"titre": c["titre"], "texte": c["texte"], "image": c["image"].pk if c["image"] else None}
                for c in section.colonnes()
            ],
            "liens": liens,
        })
    return bloc("section", {
        "title": section.title,
        "text": section.text,
        "image": section.image_id,
        "image_position": section.image_position,
        "taille_image": section.taille_image,
        "liens": liens,
    })


def contenu_page_libre(page):
    """Le contenu d'une page libre, sous forme de blocs d'onglet."""
    blocs = [bloc("entete", {
        "logo": page.logo_id, "titre": page.titre_affiche or page.title, "sous_titre": page.sous_titre,
    })]
    blocs += [section_en_bloc(s) for s in page.sections.all()]
    images = list(page.galerie_images.all())
    if images:
        blocs.append(bloc("galerie", {
            "titre": page.titre_galerie,
            "images": [{"image": i.image_id, "legende": i.legende} for i in images],
        }))
    return blocs


class Command(BaseCommand):
    help = "Transforme les liens de la page Info vers des pages libres en onglets (une seule fois)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Affiche les changements sans les enregistrer.")

    def handle(self, *args, dry_run=False, **options):
        info = InfoPage.objects.filter(slug=SLUG_INFO).first()
        if info is None:
            self.stdout.write(f"Pas de page d'informations « {SLUG_INFO} » : rien à convertir.")
            return
        if info.onglets.exists():
            self.stdout.write("La page Info a déjà ses onglets : rien à convertir.")
            return

        pages_libres = self._pages_liees(info)
        if not pages_libres:
            self.stdout.write("Aucun lien de la page Info vers une page libre : rien à convertir.")
            return
        if info.has_unpublished_changes:
            # Publier la conversion écraserait le brouillon en cours
            self.stderr.write(self.style.WARNING(
                "La page Info a un brouillon non publié : publiez-le ou annulez-le, "
                "puis relancez cette commande. Rien n'a été converti."
            ))
            return

        intro, onglets = self._repartir(info, pages_libres)
        for onglet in onglets[MAX_ONGLETS:]:
            intro += onglet["origine"]
            self.stderr.write(self.style.WARNING(
                f"Plus de {MAX_ONGLETS} onglets : « {onglet['titre']} » reste dans l'introduction."
            ))
        onglets = onglets[:MAX_ONGLETS]
        ancres = ancres_onglets(o["titre"] for o in onglets)

        for onglet, ancre in zip(onglets, ancres):
            self.stdout.write(f"Onglet « {onglet['titre']} » → {info.url}#{ancre}")
        if dry_run:
            self.stdout.write("Simulation : rien n'a été enregistré.")
            return

        with transaction.atomic():
            info.body = json.dumps(intro)
            for ordre, onglet in enumerate(onglets):
                info.onglets.add(InfoOnglet(titre=onglet["titre"], contenu=json.dumps(onglet["blocs"]), sort_order=ordre))
            info.save_revision(log_action=True).publish()
            converties = [(o["page"], a) for o, a in zip(onglets, ancres) if o["page"]]
            for page, ancre in converties:
                self._preparer_redirection(page, f"{info.url}#{ancre}")

        self.stdout.write(self.style.SUCCESS(f"Page Info convertie : {len(onglets)} onglet(s)."))
        for page, _ancre in converties:
            self._signaler_references(page)
        if converties:
            self.stdout.write("Vérifiez les onglets, puis supprimez les pages libres devenues inutiles dans Wagtail.")

    def _pages_liees(self, info):
        """Pages libres publiées et publiques liées par un bloc « lien utile »."""
        ids = [b["value"].get("page") for b in info.body.raw_data if b["type"] == "useful_link"]
        pages = {}
        for page in PageLibre.objects.filter(pk__in=[i for i in ids if i]):
            if page.live and not page.get_view_restrictions().exists():
                pages[page.pk] = page
            else:
                self.stderr.write(self.style.WARNING(
                    f"« {page.title} » n'est pas publique : elle reste un lien, à vérifier."
                ))
        return pages

    def _repartir(self, info, pages_libres):
        """Sépare le corps de la page en introduction et onglets, dans l'ordre."""
        intro, onglets, courant = [], [], None

        def fermer():
            nonlocal courant
            if courant is None:
                return
            if courant["blocs"]:
                onglets.append(courant)
            else:
                intro.extend(courant["origine"])  # titre seul : il reste en introduction
            courant = None

        for b in info.body.raw_data:
            if b["type"] == "heading" and RE_SEPARATEUR.match(b["value"]):
                continue
            if b["type"] == "heading" and len(b["value"]) <= LONGUEUR_TITRE:
                fermer()
                courant = {"titre": b["value"], "blocs": [], "origine": [b], "page": None}
            elif b["type"] == "useful_link" and b["value"].get("page") in pages_libres:
                fermer()
                page = pages_libres[b["value"]["page"]]
                titre = (b["value"]["title"] or page.title)[:LONGUEUR_TITRE]
                onglets.append({"titre": titre, "blocs": contenu_page_libre(page), "origine": [b], "page": page})
            elif courant is not None:
                courant["blocs"].append(b)
                courant["origine"].append(b)
            else:
                intro.append(b)
        fermer()
        return intro, onglets

    def _preparer_redirection(self, page, cible):
        parties = page.get_url_parts()
        if parties is None:
            return
        site_id, _racine, chemin = parties
        Redirect.objects.get_or_create(
            old_path=Redirect.normalise_path(chemin), site_id=site_id, defaults={"redirect_link": cible},
        )

    def _signaler_references(self, page):
        for objet, _references in ReferenceIndex.get_grouped_references_to(page):
            self.stdout.write(f"« {page.title} » est encore citée par : {objet}")
