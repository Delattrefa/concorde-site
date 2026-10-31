"""
Tests de la page d'informations à onglets et de sa conversion depuis les
liens vers des pages libres.

Lancement : python manage.py test info
"""
import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from wagtail.contrib.redirects.models import Redirect
from wagtail.images.tests.utils import get_test_image_file
from wagtail.images import get_image_model
from wagtail.models import Page, PageViewRestriction, Site
from wagtail.test.utils.form_data import inline_formset, nested_form_data, streamfield

from page_libre.models import PageLibre, PageLibreImage, PageLibreSection

from .models import MAX_ONGLETS, InfoOnglet, InfoPage, ancres_onglets


def convertir(*options):
    sortie, erreurs = StringIO(), StringIO()
    call_command("convertir_info_en_onglets", *options, stdout=sortie, stderr=erreurs)
    return sortie.getvalue(), erreurs.getvalue()


class Base(TestCase):
    def setUp(self):
        Site.clear_site_root_paths_cache()  # laissé par les tests d'autres applications
        self.racine = Page.objects.get(depth=2)

    def info(self, corps, slug="info"):
        page = InfoPage(title="Info", slug=slug, body=json.dumps(corps))
        self.racine.add_child(instance=page)
        page.save_revision().publish()
        return InfoPage.objects.get(pk=page.pk)

    def page_libre(self, titre="Le Blé qui Lève", **champs):
        page = PageLibre(title=titre, **champs)
        self.racine.add_child(instance=page)
        return page

    def lien(self, page, titre="La troupe"):
        return {"type": "useful_link", "value": {"title": titre, "page": page.pk, "url": ""}}


class ConversionTests(Base):
    def test_liens_et_titres_deviennent_des_onglets(self):
        image = get_image_model().objects.create(title="Photo", file=get_test_image_file())
        libre = self.page_libre(logo=image, titre_affiche="L'histoire", sous_titre="Depuis 1970", titre_galerie="Affiches")
        PageLibreSection.objects.create(page=libre, title="Débuts", text="<p>Le cercle</p>", image=image, sort_order=0)
        PageLibreSection.objects.create(
            page=libre, type_section="colonnes", titre_colonnes="Saisons", nombre_colonnes=2,
            colonne_1_titre="Un", colonne_2_titre="Deux", colonne_3_titre="Ignorée", sort_order=1,
        )
        PageLibreImage.objects.create(page=libre, image=image, legende="Affiche 2023")
        info = self.info([
            {"type": "heading", "value": "Toutes les infos de l'ASBL."},
            {"type": "heading", "value": "Historique"},
            {"type": "paragraph", "value": "<p>Fondée en 1970</p>"},
            self.lien(libre),
            {"type": "heading", "value": "--------"},
        ])

        convertir()

        info = InfoPage.objects.get(pk=info.pk)
        self.assertEqual([b.value for b in info.body], ["Toutes les infos de l'ASBL."])
        historique, troupe = info.onglets.all()
        self.assertEqual((historique.titre, troupe.titre), ("Historique", "La troupe"))
        self.assertEqual([b.block_type for b in troupe.contenu], ["entete", "section", "colonnes", "galerie"])
        self.assertEqual(troupe.contenu[2].value.nombre_colonnes, 2)

        reponse = self.client.get(info.url)
        self.assertContains(reponse, 'role="tab"', count=2)
        for texte in ("Fondée en 1970", "L&#x27;histoire", "Depuis 1970", "Le cercle", "Saisons", "Affiche 2023"):
            self.assertContains(reponse, texte)
        self.assertNotContains(reponse, "Ignorée")
        self.assertNotContains(reponse, "--------")

        # La page libre reste en ligne ; une fois supprimée, son adresse mène à l'onglet
        self.assertEqual(self.client.get(libre.url).status_code, 200)
        ancienne_adresse = libre.url
        libre.delete()
        arrivee = self.client.get(ancienne_adresse)
        self.assertRedirects(arrivee, f"{info.url}#onglet-la-troupe", status_code=301, fetch_redirect_response=False)

    def test_une_seule_fois(self):
        libre = self.page_libre()
        info = self.info([self.lien(libre)])
        convertir()
        # Un lien ajouté ensuite, volontairement, reste un lien
        info.body = json.dumps([self.lien(libre, "Lien voulu")])
        info.save_revision().publish()
        sortie, _ = convertir()
        self.assertIn("déjà", sortie)
        info = InfoPage.objects.get(pk=info.pk)
        self.assertEqual(info.onglets.count(), 1)
        self.assertEqual(info.body[0].block_type, "useful_link")

    def test_simulation_sans_effet(self):
        info = self.info([self.lien(self.page_libre())])
        sortie, _ = convertir("--dry-run")
        self.assertIn("Simulation", sortie)
        self.assertFalse(info.onglets.exists())
        self.assertEqual(InfoPage.objects.get(pk=info.pk).body[0].block_type, "useful_link")
        self.assertFalse(Redirect.objects.exists())

    def test_autres_pages_et_liens_externes_intacts(self):
        libre = self.page_libre()
        politique = self.info([self.lien(libre), {"type": "heading", "value": "Vos droits"},
                               {"type": "paragraph", "value": "<p>RGPD</p>"}], slug="politique-de-confidentialite")
        externe = {"type": "useful_link", "value": {"title": "Commune", "page": None, "url": "https://exemple.be/"}}
        info = self.info([externe, self.lien(libre)])
        convertir()
        self.assertFalse(politique.onglets.exists())
        info = InfoPage.objects.get(pk=info.pk)
        self.assertEqual(info.body[0].value["title"], "Commune")
        self.assertEqual(info.onglets.count(), 1)

    def test_page_non_publique_reste_un_lien(self):
        brouillon = self.page_libre("Brouillon", live=False)
        privee = self.page_libre("Privée")
        PageViewRestriction.objects.create(page=privee, restriction_type="login")
        publique = self.page_libre("Publique")
        info = self.info([self.lien(brouillon), self.lien(privee), self.lien(publique)])
        _, erreurs = convertir()
        self.assertIn("Brouillon", erreurs)
        self.assertIn("Privée", erreurs)
        info = InfoPage.objects.get(pk=info.pk)
        self.assertEqual(info.onglets.count(), 1)
        self.assertEqual(len(info.body), 2)

    def test_brouillon_de_la_page_info_preserve(self):
        info = self.info([self.lien(self.page_libre())])
        info.title = "Info modifiée"
        info.save_revision()
        _, erreurs = convertir()
        self.assertIn("brouillon", erreurs)
        info = InfoPage.objects.get(pk=info.pk)
        self.assertFalse(info.onglets.exists())
        self.assertEqual(info.get_latest_revision_as_object().title, "Info modifiée")

    def test_limite_de_8_onglets(self):
        pages = [self.page_libre(f"Page {i}") for i in range(MAX_ONGLETS + 2)]
        info = self.info([self.lien(p, f"Lien {i}") for i, p in enumerate(pages)])
        _, erreurs = convertir()
        info = InfoPage.objects.get(pk=info.pk)
        self.assertEqual(info.onglets.count(), MAX_ONGLETS)
        self.assertEqual([b.value["title"] for b in info.body], ["Lien 8", "Lien 9"])
        self.assertIn("Lien 8", erreurs)


class AffichageTests(Base):
    def test_sans_onglet_affichage_inchange(self):
        info = self.info([{"type": "paragraph", "value": "<p>Mentions</p>"}])
        reponse = self.client.get(info.url)
        self.assertContains(reponse, "Mentions")
        self.assertNotContains(reponse, 'role="tab"')
        self.assertNotContains(reponse, "onglets.js")

    def test_premier_onglet_visible_et_ancres_distinctes(self):
        info = self.info([])
        for ordre, titre in enumerate(["Été", "Été", "Tarifs"]):
            InfoOnglet.objects.create(page=info, titre=titre, sort_order=ordre)
        reponse = self.client.get(info.url)
        self.assertEqual(ancres_onglets(["Été", "Été", "Tarifs"]), ["onglet-ete", "onglet-ete-2", "onglet-tarifs"])
        self.assertContains(reponse, 'aria-selected="true"', count=1)
        self.assertContains(reponse, 'id="onglet-ete" aria-labelledby="onglet-ete-titre">')
        self.assertContains(reponse, 'id="onglet-tarifs" aria-labelledby="onglet-tarifs-titre" hidden>')

    def test_admin_refuse_plus_de_8_onglets(self):
        info = self.info([])
        admin = get_user_model().objects.create_superuser("admin", "admin@exemple.be", "mdp")
        self.client.force_login(admin)

        def envoyer(nombre):
            return self.client.post(reverse("wagtailadmin_pages:edit", args=[info.pk]), nested_form_data({
                "title": "Info", "slug": "info", "body": streamfield([]),
                "onglets": inline_formset([{"titre": f"O{i}", "contenu": streamfield([])} for i in range(nombre)]),
                "action-publish": "1",
            }))

        envoyer(MAX_ONGLETS + 1)
        self.assertEqual(info.onglets.count(), 0)
        envoyer(MAX_ONGLETS)
        self.assertEqual(info.onglets.count(), MAX_ONGLETS)
