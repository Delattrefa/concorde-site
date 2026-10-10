"""
Tests du contrat de location en PDF (calendrier/contrats.py et vues
rediger_contrat, telecharger_contrat, apercu_modele_contrat).

Les PDF générés sont relus avec pypdf pour vérifier leur contenu réel
(texte, nombre de pages, images).

Lancement : python manage.py test calendrier
"""
import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image as ImagePIL
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from wagtail.images import get_image_model
from wagtail.models import Collection

from .contrats import (
    _ligne_en_balisage, _mise_en_forme_date, _montant, _texte_vers_elements,
    generer_pdf_contrat, nom_fichier_contrat, variables_inconnues,
)
from .forms import NOM_COLLECTION_SIGNATURES
from .models import AnnexeContrat, ArticleContrat, ContratLocation, MiseEnPageContrat, Reservation


def _pdf(*pages):
    """PDF d'une page par texte donné (texte vide = page blanche)."""
    tampon = io.BytesIO()
    dessin = canvas.Canvas(tampon, pagesize=A4)
    for texte in pages:
        if texte:
            dessin.drawString(100, 700, texte)
        dessin.showPage()
    dessin.save()
    return tampon.getvalue()


def _png(largeur=300, hauteur=100):
    tampon = io.BytesIO()
    ImagePIL.new("RGB", (largeur, hauteur), "navy").save(tampon, format="PNG")
    return tampon.getvalue()


def _texte(contenu_pdf):
    """Texte du PDF, espaces normalisés (le PDF coupe les lignes)."""
    lecteur = PdfReader(io.BytesIO(contenu_pdf))
    return " ".join(" ".join((page.extract_text() or "").split()) for page in lecteur.pages)


def _pages(contenu_pdf):
    return PdfReader(io.BytesIO(contenu_pdf)).pages


# ══════════════════════════════════════════════════════════════════════════════
#  MISE EN FORME DU TEXTE
# ══════════════════════════════════════════════════════════════════════════════

class MiseEnFormeTests(SimpleTestCase):

    def test_date_en_francais(self):
        self.assertEqual(_mise_en_forme_date(date(2026, 10, 7)), "7 octobre 2026")
        self.assertEqual(_mise_en_forme_date(date(2027, 2, 1)), "1 février 2027")

    def test_montant_au_format_belge(self):
        self.assertEqual(_montant(Decimal("350")), "350,00")
        self.assertEqual(_montant(Decimal("1350.5")), "1 350,50")
        self.assertEqual(_montant("à définir"), "à définir")

    def test_variables_inconnues_signalees(self):
        texte = "Loué à {locataire} du {date_debut} au {date_fn} pour {prix}."
        self.assertEqual(variables_inconnues(texte), ["date_fn", "prix"])
        self.assertEqual(variables_inconnues("{locaux}\n{delegue}"), [])

    def test_ligne_variables_gras_et_caracteres_speciaux(self):
        valeurs = {"montant_location": "350,00", "locataire": "Dupont & Fils <SRL>"}
        self.assertEqual(
            _ligne_en_balisage("**Prix** : {montant_location} € & <taxes> pour {locataire}", valeurs),
            "<b>Prix</b> : 350,00 € &amp; &lt;taxes&gt; pour Dupont &amp; Fils &lt;SRL&gt;",
        )

    def test_variable_inconnue_laissee_telle_quelle(self):
        self.assertEqual(_ligne_en_balisage("{inconnue}", {}), "{inconnue}")

    def test_paragraphes_puces_et_locaux(self):
        style = getSampleStyleSheet()["Normal"]
        texte = "Premier paragraphe\nsuite\n\n- puce 1\n- puce 2\n\n{locaux}\n\nFin"
        elements = _texte_vers_elements(texte, {}, ["Cuisine équipée"], style)
        self.assertEqual(
            [type(e).__name__ for e in elements],
            ["Paragraph", "ListFlowable", "ListFlowable", "Paragraph"],
        )

    def test_aucun_local_coche(self):
        style = getSampleStyleSheet()["Normal"]
        elements = _texte_vers_elements("{locaux}", {}, [], style)
        self.assertIsInstance(elements[0], Paragraph)
        self.assertIn("aucun local", elements[0].text)


class NomFichierTests(SimpleTestCase):

    def test_particulier(self):
        resa = Reservation(nom="Dupont", prenom="Marie", date_debut=date(2026, 10, 7))
        self.assertEqual(nom_fichier_contrat(resa), "Contrat de location - Dupont Marie - 07-10-2026.pdf")

    def test_societe_caracteres_interdits_remplaces(self):
        resa = Reservation(
            type_client=Reservation.TYPE_SOCIETE, nom_societe='Fêtes/Events: "Pro"',
            nom="Martin", prenom="Paul", date_debut=date(2026, 12, 31),
        )
        self.assertEqual(nom_fichier_contrat(resa), "Contrat de location - Fêtes-Events- -Pro- - 31-12-2026.pdf")


# ══════════════════════════════════════════════════════════════════════════════
#  GÉNÉRATION DU PDF
# ══════════════════════════════════════════════════════════════════════════════

class GenerationPdfTests(TestCase):

    def setUp(self):
        # La migration 0004 installe les annexes du PDF modèle : chaque test
        # part d'un contrat-type connu.
        AnnexeContrat.objects.all().delete()
        ArticleContrat.objects.all().delete()
        self.reservation = Reservation.objects.create(
            nom="Dupont", prenom="Marie", adresse="Rue Haute 5 & 7, 7387 Honnelles",
            email="marie@exemple.be", telephone="0470 12 34 56",
            date_debut=date(2026, 10, 7), date_fin=date(2026, 10, 8),
            statut=Reservation.STATUT_VALIDEE,
        )
        self.contrat = ContratLocation(
            reservation=self.reservation, delegue_prenom="Jean", delegue_nom="Delcourt",
            local_salle=True, local_cuisine=True,
            montant_location=Decimal("1350.50"), montant_caution=Decimal("150"),
        )
        self.article = ArticleContrat.objects.create(
            ordre=10, titre="ARTICLE 1 - OBJET",
            texte="Le propriétaire loue à {locataire} :\n\n{locaux}\n\n"
                  "du {date_debut} au {date_fin}, pour **{montant_location} €** "
                  "(caution : {montant_caution} €). Délégué : {delegue}.",
        )

    def _generer(self, **kwargs):
        return generer_pdf_contrat(self.reservation, self.contrat, **kwargs)

    def test_contenu_du_contrat(self):
        texte = _texte(self._generer())

        for attendu in [
            "CONTRAT DE LOCATION", "Marie Dupont", "Rue Haute 5 & 7, 7387 Honnelles",
            "marie@exemple.be", "Jean Delcourt", "ARTICLE 1 - OBJET",
            "Une salle des fêtes et une scène", "Cuisine équipée",
            "du 7 octobre 2026 au 8 octobre 2026", "1 350,50 €", "caution : 150,00 €",
            "Le Locataire",
        ]:
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, texte)
        self.assertNotIn("Local dénommé café", texte)       # local non coché
        self.assertNotIn("{", texte)                         # toutes les variables remplacées

    def test_societe(self):
        self.reservation.type_client = Reservation.TYPE_SOCIETE
        self.reservation.nom_societe = "Événements Martin SRL"
        self.reservation.numero_tva = "BE0123456749"

        texte = _texte(self._generer())

        self.assertIn("Événements Martin SRL", texte)
        self.assertIn("N° de TVA : BE 0123.456.749", texte)
        self.assertIn("représentée par Marie Dupont", texte)
        self.assertIn("Pour Événements Martin SRL", texte)

    def test_seuls_les_articles_actifs(self):
        ArticleContrat.objects.create(ordre=20, titre="ARTICLE RETIRÉ", texte="Ancien texte.", actif=False)
        self.assertNotIn("ARTICLE RETIRÉ", _texte(self._generer()))

    def test_sans_aucun_article(self):
        texte = _texte(self._generer(articles=[], annexes=[]))
        self.assertIn("Le Locataire", texte)

    def test_long_contrat_signatures_avec_la_fin_du_dernier_article(self):
        for i in range(2, 30):
            ArticleContrat.objects.create(
                ordre=10 * i, titre=f"ARTICLE {i}", texte=f"Clause numéro {i}. " * 40,
            )
        pages = _pages(self._generer(annexes=[]))

        self.assertGreater(len(pages), 3)
        derniere = " ".join((pages[-1].extract_text() or "").split())
        self.assertIn("Le Locataire", derniere)
        self.assertIn("Clause numéro 29.", derniere)

    def test_annexes_actives_ajoutees_sans_les_pages_vides(self):
        AnnexeContrat.objects.create(
            ordre=10, titre="Annexe I",
            fichier=SimpleUploadedFile("annexe1.pdf", _pdf(
                "ANNEXE I - Liste du mobilier", "", "ANNEXE I - Liste de la vaisselle",
            )),
        )
        AnnexeContrat.objects.create(
            ordre=20, titre="Annexe désactivée", actif=False,
            fichier=SimpleUploadedFile("annexe2.pdf", _pdf("ANNEXE RETIRÉE - ancien tarif")),
        )
        nb_pages_contrat = len(_pages(self._generer(annexes=[])))

        contenu = self._generer()

        self.assertEqual(len(_pages(contenu)), nb_pages_contrat + 2)
        texte = _texte(contenu)
        self.assertIn("ANNEXE I - Liste du mobilier", texte)
        self.assertIn("ANNEXE I - Liste de la vaisselle", texte)
        self.assertNotIn("ANNEXE RETIRÉE", texte)

    def test_page_d_annexe_avec_seulement_le_pied_de_page_retiree(self):
        AnnexeContrat.objects.create(
            ordre=10, titre="Annexe I",
            fichier=SimpleUploadedFile("annexe.pdf", _pdf(
                "ANNEXE I - Liste du mobilier",
                "ASBL LA CONCORDE - www.la-concorde.be - page 2/2",
            )),
        )
        nb_pages_contrat = len(_pages(self._generer(annexes=[])))
        self.assertEqual(len(_pages(self._generer())), nb_pages_contrat + 1)

    def test_sans_annexe_enregistree_reprend_celles_du_modele(self):
        nb_pages_contrat = len(_pages(self._generer(annexes=[])))
        self.assertGreater(len(_pages(self._generer())), nb_pages_contrat)

    def test_signature_et_image_d_en_tete(self):
        sans_images = _pages(self._generer(annexes=[]))
        self.assertEqual(sum(len(p.images) for p in sans_images), 0)

        racine = Collection.get_first_root_node()
        collection = racine.add_child(name=NOM_COLLECTION_SIGNATURES)
        self.contrat.signature = get_image_model().objects.create(
            title="Signature Jean", collection=collection,
            file=SimpleUploadedFile("signature.png", _png(), content_type="image/png"),
        )
        mise_en_page = MiseEnPageContrat.charger()
        mise_en_page.image_entete = SimpleUploadedFile("entete.png", _png(2000, 450), content_type="image/png")
        mise_en_page.save()

        pages = _pages(self._generer(annexes=[]))
        self.assertGreaterEqual(len(pages[0].images), 1)                  # en-tête
        self.assertGreaterEqual(len(pages[-1].images), 1)                 # signature


# ══════════════════════════════════════════════════════════════════════════════
#  VUES : RÉDACTION, TÉLÉCHARGEMENT, APERÇU
# ══════════════════════════════════════════════════════════════════════════════

class VuesContratTests(TestCase):

    def setUp(self):
        self.admin = get_user_model().objects.create_user("admin", password="mdp", is_staff=True)
        self.client.force_login(self.admin)
        jour = date.today() + timedelta(days=30)
        self.reservation = Reservation.objects.create(
            nom="Dupont", prenom="Marie", adresse="Rue Haute 5, 7387 Honnelles",
            email="marie@exemple.be", telephone="0470 12 34 56",
            date_debut=jour, date_fin=jour, statut=Reservation.STATUT_VALIDEE,
        )
        self.url_rediger = reverse("calendrier:reservation_contrat", args=[self.reservation.pk])
        self.url_pdf = reverse("calendrier:reservation_contrat_pdf", args=[self.reservation.pk])

    def _rediger(self, **champs):
        donnees = {
            "delegue_prenom": "Jean", "delegue_nom": "Delcourt", "local_salle": "on",
            "montant_location": "350", "montant_caution": "150",
        }
        donnees.update(champs)
        return self.client.post(self.url_rediger, donnees)

    def test_contrat_refuse_pour_une_reservation_non_validee(self):
        self.reservation.statut = Reservation.STATUT_ATTENTE
        self.reservation.save()

        reponse = self._rediger()

        self.assertRedirects(reponse, reverse("calendrier:reservation_detail", args=[self.reservation.pk]))
        self.assertFalse(ContratLocation.objects.exists())

    def test_generation_telechargement_et_copie_conservee(self):
        reponse = self._rediger()

        self.assertEqual(reponse["Content-Type"], "application/pdf")
        self.assertIn(nom_fichier_contrat(self.reservation), reponse["Content-Disposition"])
        self.assertIn("Jean Delcourt", _texte(reponse.content))

        contrat = ContratLocation.objects.get(reservation=self.reservation)
        self.assertEqual(contrat.genere_par, self.admin)
        self.assertTrue(contrat.fichier_disponible)

        telechargement = self.client.get(self.url_pdf)
        self.assertEqual(telechargement.status_code, 200)
        self.assertEqual(b"".join(telechargement.streaming_content), reponse.content)

    def test_regeneration_remplace_le_pdf_et_garde_le_suivi_des_paiements(self):
        self._rediger()
        ContratLocation.objects.filter(reservation=self.reservation).update(location_payee=True)

        reponse = self._rediger(delegue_nom="Lambert", montant_location="400")

        self.assertEqual(ContratLocation.objects.count(), 1)
        contrat = ContratLocation.objects.get()
        self.assertEqual((contrat.delegue_nom, contrat.montant_location), ("Lambert", Decimal("400")))
        self.assertTrue(contrat.location_payee)
        texte = _texte(b"".join(self.client.get(self.url_pdf).streaming_content))
        self.assertIn("Jean Lambert", texte)
        self.assertEqual(_texte(reponse.content), texte)

    def test_formulaire_invalide_aucun_contrat(self):
        reponse = self._rediger(montant_location="")
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(ContratLocation.objects.exists())

    def test_telechargement_sans_contrat_ou_fichier_absent(self):
        self.assertEqual(self.client.get(self.url_pdf).status_code, 404)

        self._rediger()
        contrat = ContratLocation.objects.get()
        contrat.fichier_pdf.storage.delete(contrat.fichier_pdf.name)
        self.assertEqual(self.client.get(self.url_pdf).status_code, 404)

    def test_nouveau_contrat_propose_la_derniere_signature(self):
        collection = Collection.get_first_root_node().add_child(name=NOM_COLLECTION_SIGNATURES)
        signature = get_image_model().objects.create(
            title="Signature Jean", collection=collection,
            file=SimpleUploadedFile("signature.png", _png(), content_type="image/png"),
        )
        autre = Reservation.objects.create(
            nom="Martin", prenom="Paul", adresse="Rue Basse 1", email="paul@exemple.be",
            telephone="0470 00 00 00", date_debut=self.reservation.date_debut + timedelta(days=7),
            date_fin=self.reservation.date_debut + timedelta(days=7), statut=Reservation.STATUT_VALIDEE,
        )
        ContratLocation.objects.create(
            reservation=autre, delegue_prenom="Jean", delegue_nom="Delcourt",
            montant_location=Decimal("300"), signature=signature,
        )

        reponse = self.client.get(self.url_rediger)

        self.assertEqual(reponse.context["form"].initial.get("signature"), signature.pk)

    def test_apercu_du_contrat_type(self):
        reponse = self.client.get(reverse("calendrier:modele_contrat_apercu"))

        self.assertEqual(reponse["Content-Type"], "application/pdf")
        texte = _texte(reponse.content)
        self.assertIn("NOM DU LOCATAIRE", texte)
        self.assertIn("NOM DU DÉLÉGUÉ", texte)


class AnnexeInvalideTests(TestCase):

    def test_fichier_qui_n_est_pas_un_pdf_refuse(self):
        admin = get_user_model().objects.create_user("admin", password="mdp", is_staff=True)
        self.client.force_login(admin)
        nb_annexes = AnnexeContrat.objects.count()

        reponse = self.client.post(reverse("calendrier:annexe_contrat_ajouter"), {
            "titre": "Annexe piégée", "ordre": "50", "actif": "on",
            "fichier": SimpleUploadedFile("faux.pdf", b"ceci n'est pas un PDF", content_type="application/pdf"),
        })

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "pas un PDF valide")
        self.assertEqual(AnnexeContrat.objects.count(), nb_annexes)

    def test_pdf_sans_page_refuse(self):
        admin = get_user_model().objects.create_user("admin", password="mdp", is_staff=True)
        self.client.force_login(admin)
        tampon = io.BytesIO()
        PdfWriter().write(tampon)

        reponse = self.client.post(reverse("calendrier:annexe_contrat_ajouter"), {
            "titre": "Annexe vide", "ordre": "50", "actif": "on",
            "fichier": SimpleUploadedFile("vide.pdf", tampon.getvalue(), content_type="application/pdf"),
        })

        self.assertContains(reponse, "aucune page")
