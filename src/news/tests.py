"""
Tests des actualités proposées depuis le site : publication immédiate pour
les administrateurs, validation (circuit Wagtail « Moderators approval »)
pour les autres membres, droits de l'auteur.

Case « À la une » : actualité affichée en priorité sur la page d'accueil.

Éditeur par blocs : conversion du contenu, nettoyage du texte enrichi,
images positionnées et envoi des photos.

Lancement : python manage.py test news
"""
import io
import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image as ImagePIL
from wagtail.images.models import Image
from wagtail.models import Page, Site, WorkflowPage, WorkflowState

from home.models import HomePage
from home.slugs import slug_ascii

from .editeur import nettoyer_texte_enrichi
from .models import NewsIndexPage, NewsPage


def _corps(*blocs):
    """Champ « corps » tel que l'envoie l'éditeur JavaScript."""
    return json.dumps([{"type": type_bloc, "value": valeur} for type_bloc, valeur in blocs])


def _photo(nom="photo.png"):
    tampon = io.BytesIO()
    ImagePIL.new("RGB", (40, 30), "navy").save(tampon, format="PNG")
    return SimpleUploadedFile(nom, tampon.getvalue(), content_type="image/png")


def _image_wagtail(titre="Photo"):
    return Image.objects.create(title=titre, file=_photo())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ValidationActualitesTests(TestCase):

    def setUp(self):
        Utilisateur = get_user_model()
        self.membre = Utilisateur.objects.create_user("membre", "membre@exemple.be", "mdp")
        self.autre_membre = Utilisateur.objects.create_user("autre", "autre@exemple.be", "mdp")
        self.admin = Utilisateur.objects.create_user("admin", "admin@exemple.be", "mdp", is_staff=True)
        # Droit Wagtail de publier (groupe créé par les migrations de Wagtail)
        self.admin.groups.add(Group.objects.get(name="Moderators"))
        self.superadmin = Utilisateur.objects.create_superuser("super", "super@exemple.be", "mdp")

        racine = Page.objects.get(depth=1)
        self.index = racine.add_child(instance=NewsIndexPage(title="Actualités", slug="actualites"))
        Site.objects.all().delete()
        Site.objects.create(hostname="testserver", root_page=self.index, is_default_site=True)

    # ── Outils ────────────────────────────────────────────────────────────

    def _proposer(self, utilisateur, titre="Fête du village"):
        self.client.force_login(utilisateur)
        reponse = self.client.post(reverse("news_ajouter"), {
            "titre": titre, "date": "2026-10-17", "intro": "Résumé",
            "corps": _corps(("paragraph", "<p>Texte de l'actualité.</p>")),
        })
        return reponse, NewsPage.objects.get(draft_title=titre)

    def _modifier(self, news, titre):
        return self.client.post(reverse("news_modifier", args=[news.pk]), {
            "titre": titre, "date": "2026-10-17", "intro": "Résumé modifié",
            "corps": _corps(("paragraph", "<p>Nouveau texte.</p>")),
        })

    def _approuver(self, news):
        """Approbation par un super-utilisateur, comme depuis l'admin Wagtail."""
        etat_tache = news.current_workflow_state.current_task_state
        etat_tache.task.specific.on_action(etat_tache, self.superadmin, "approve")

    def _visible_sur_le_site(self, news):
        self.client.logout()
        return self.client.get(news.url).status_code == 200

    def _actualite_en_ligne(self, utilisateur, titre="Concert de printemps"):
        """Actualité proposée par `utilisateur` puis approuvée."""
        _, news = self._proposer(utilisateur, titre)
        if news.current_workflow_state:
            self._approuver(news)
        news.refresh_from_db()
        self.assertTrue(news.live)
        return news

    # ── Administrateur : publication immédiate ────────────────────────────

    def test_administrateur_publie_immediatement(self):
        reponse, news = self._proposer(self.admin)

        self.assertTrue(news.live)
        self.assertRedirects(reponse, news.url, fetch_redirect_response=False)
        self.assertIsNone(news.current_workflow_state)
        self.assertTrue(self._visible_sur_le_site(news))

    def test_administrateur_du_calendrier_sans_droit_de_publier_passe_par_la_validation(self):
        """is_staff (calendrier, modification de toutes les actualités depuis
        le site) sans le droit Wagtail de publier : ses actualités et ses
        modifications attendent la validation."""
        gestionnaire = get_user_model().objects.create_user("calendrier", "cal@exemple.be", "mdp", is_staff=True)
        _reponse, la_sienne = self._proposer(gestionnaire, titre="Souper")
        self.assertFalse(la_sienne.live)
        self.assertEqual(la_sienne.current_workflow_state.status, WorkflowState.STATUS_IN_PROGRESS)
        self.assertContains(self.client.get(self.index.url), "Proposer une actualité")

        _reponse, news = self._proposer(self.admin)
        self.client.force_login(gestionnaire)
        self._modifier(news, "Titre corrigé")
        news.refresh_from_db()
        self.assertEqual(news.title, "Fête du village")  # version en ligne inchangée
        self.assertEqual(news.current_workflow_state.status, WorkflowState.STATUS_IN_PROGRESS)

    # ── Membre : validation obligatoire ───────────────────────────────────

    def test_membre_actualite_en_attente_de_validation(self):
        reponse, news = self._proposer(self.membre)

        self.assertFalse(news.live)
        self.assertRedirects(reponse, self.index.url, fetch_redirect_response=False)
        self.assertEqual(news.current_workflow_state.status, WorkflowState.STATUS_IN_PROGRESS)
        self.assertFalse(self._visible_sur_le_site(news))
        self.assertNotContains(self.client.get(self.index.url), "Fête du village")

    def test_moderateurs_prevenus_par_e_mail(self):
        self._proposer(self.membre)
        destinataires = {adresse for message in mail.outbox for adresse in message.to}
        self.assertIn("super@exemple.be", destinataires)
        self.assertNotIn("membre@exemple.be", destinataires)

    def test_publiee_apres_approbation(self):
        _, news = self._proposer(self.membre)

        self._approuver(news)

        news.refresh_from_db()
        self.assertTrue(news.live)
        self.assertTrue(self._visible_sur_le_site(news))

    def test_modification_d_une_actualite_en_ligne_soumise_a_validation(self):
        news = self._actualite_en_ligne(self.membre)

        self.client.force_login(self.membre)
        reponse = self._modifier(news, "Concert annulé !")

        self.assertRedirects(reponse, self.index.url, fetch_redirect_response=False)
        news.refresh_from_db()
        self.assertEqual(news.title, "Concert de printemps")     # version en ligne inchangée
        self.assertTrue(news.has_unpublished_changes)

        self._approuver(news)
        news.refresh_from_db()
        self.assertEqual(news.title, "Concert annulé !")

    def test_modification_pendant_la_relecture_relance_la_validation(self):
        _, news = self._proposer(self.membre, "Première version")
        premiere_validation = news.current_workflow_state

        self._modifier(news, "Seconde version")

        news.refresh_from_db()
        premiere_validation.refresh_from_db()
        self.assertEqual(premiere_validation.status, WorkflowState.STATUS_CANCELLED)
        self.assertEqual(news.current_workflow_state.status, WorkflowState.STATUS_IN_PROGRESS)
        self._approuver(news)
        news.refresh_from_db()
        self.assertEqual((news.live, news.title), (True, "Seconde version"))

    def test_formulaire_de_modification_reprend_la_version_en_attente(self):
        news = self._actualite_en_ligne(self.membre)
        self.client.force_login(self.membre)
        self._modifier(news, "Titre en attente")

        reponse = self.client.get(reverse("news_modifier", args=[news.pk]))

        self.assertEqual(reponse.context["form"].initial["titre"], "Titre en attente")

    def test_administrateur_modifie_et_publie_directement(self):
        news = self._actualite_en_ligne(self.admin)
        self.client.force_login(self.admin)

        self._modifier(news, "Corrigé")

        news.refresh_from_db()
        self.assertEqual((news.title, news.has_unpublished_changes), ("Corrigé", False))

    def test_sans_circuit_de_validation_reste_en_brouillon(self):
        WorkflowPage.objects.all().delete()

        _, news = self._proposer(self.membre)

        self.assertFalse(news.live)
        self.assertIsNone(news.current_workflow_state)

    # ── Liste « en attente » et droits de l'auteur ────────────────────────

    def test_l_auteur_voit_ses_actualites_en_attente(self):
        self._proposer(self.membre, "Ma proposition")

        self.client.force_login(self.membre)
        reponse = self.client.get(self.index.url)
        self.assertContains(reponse, "Vos actualités en attente de validation")
        self.assertContains(reponse, "Ma proposition")

        self.client.force_login(self.autre_membre)
        self.assertNotContains(self.client.get(self.index.url), "Ma proposition")

    def test_seul_l_auteur_peut_modifier_ou_supprimer(self):
        _, news = self._proposer(self.membre)

        self.client.force_login(self.autre_membre)
        self.assertEqual(self._modifier(news, "Piraté").status_code, 403)
        self.assertEqual(self.client.post(reverse("news_supprimer", args=[news.pk])).status_code, 403)

        self.client.force_login(self.membre)
        self.client.post(reverse("news_supprimer", args=[news.pk]))
        self.assertFalse(NewsPage.objects.filter(pk=news.pk).exists())

    def test_proposer_reserve_aux_membres_connectes(self):
        reponse = self.client.get(reverse("news_ajouter"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("login"), reponse.url)

    def test_textes_du_formulaire_selon_le_profil(self):
        self.client.force_login(self.membre)
        self.assertContains(self.client.get(reverse("news_ajouter")), "Envoyer pour validation")

        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("news_ajouter")), "Publier l'actualité")

    # ── Administrateur : modification de toutes les actualités ────────────

    def _actualite_wagtail(self, titre, body):
        """Actualité créée dans l'admin Wagtail (cree_par vide), en ligne."""
        news = self.index.add_child(instance=NewsPage(title=titre, slug=slug_ascii(titre), date=date.today()))
        news.body = body
        news.save_revision().publish()
        return NewsPage.objects.get(pk=news.pk)

    def test_administrateur_modifie_une_actualite_creee_dans_wagtail(self):
        news = self._actualite_wagtail("Brocante", [("paragraph", "<p>Texte simple</p>")])
        self.client.force_login(self.admin)

        formulaire = self.client.get(reverse("news_modifier", args=[news.pk]))
        self.assertEqual(json.loads(formulaire.context["form"].initial["corps"]),
                         [{"type": "paragraph", "value": "<p>Texte simple</p>"}])
        self.assertNotContains(formulaire, "Supprimer cette actualité")

        reponse = self._modifier(news, "Grande brocante")
        news.refresh_from_db()
        self.assertRedirects(reponse, news.url, fetch_redirect_response=False)
        self.assertEqual(news.title, "Grande brocante")
        self.assertEqual(self.client.post(reverse("news_supprimer", args=[news.pk])).status_code, 403)

    def test_administrateur_publie_l_actualite_d_un_membre_en_relecture(self):
        _, news = self._proposer(self.membre)
        self.client.force_login(self.admin)

        self._modifier(news, "Fête du village corrigée")
        news.refresh_from_db()
        self.assertTrue(news.live)
        self.assertEqual(news.title, "Fête du village corrigée")
        self.assertIsNone(news.current_workflow_state)
        self.assertEqual(news.cree_par, self.membre)

    def test_membre_ne_modifie_pas_une_actualite_creee_dans_wagtail(self):
        news = self._actualite_wagtail("Brocante", [])
        self.client.force_login(self.membre)
        self.assertEqual(self._modifier(news, "Piraté").status_code, 403)


class ALaUneTests(TestCase):
    """Case « À la une » : l'actualité cochée remplace la plus récente sur
    la page d'accueil, quelle que soit sa date."""

    def setUp(self):
        racine = Page.objects.get(depth=1)
        self.accueil = racine.add_child(instance=HomePage(title="Accueil", slug="accueil-test"))
        self.index = self.accueil.add_child(instance=NewsIndexPage(title="Actualités", slug="actualites"))
        Site.objects.all().delete()
        Site.objects.create(hostname="testserver", root_page=self.accueil, is_default_site=True)
        self.admin = get_user_model().objects.create_user("admin", "admin@exemple.be", "mdp", is_staff=True)
        # Droit Wagtail de publier (groupe créé par les migrations de Wagtail)
        self.admin.groups.add(Group.objects.get(name="Moderators"))

    def _actualite(self, titre, il_y_a_jours, a_la_une=False):
        return self.index.add_child(instance=NewsPage(
            title=titre, slug=slug_ascii(titre),
            date=date.today() - timedelta(days=il_y_a_jours), a_la_une=a_la_une,
        ))

    def _accueil(self):
        return self.client.get(self.accueil.url)

    def test_sans_a_la_une_la_plus_recente(self):
        self._actualite("Ancienne", 10)
        self._actualite("Récente", 2)

        reponse = self._accueil()
        self.assertEqual(reponse.context["derniere_actualite"].title, "Récente")
        self.assertContains(reponse, "Dernière actualité")

    def test_a_la_une_passe_avant_la_plus_recente_meme_ancienne(self):
        self._actualite("Concert d'été", 90, a_la_une=True)
        self._actualite("Récente", 2)

        reponse = self._accueil()
        self.assertEqual(reponse.context["derniere_actualite"].title, "Concert d'été")
        self.assertContains(reponse, "À la une")

    def test_plusieurs_a_la_une_la_plus_recente_l_emporte(self):
        self._actualite("Première", 20, a_la_une=True)
        self._actualite("Seconde", 5, a_la_une=True)

        self.assertEqual(self._accueil().context["derniere_actualite"].title, "Seconde")

    def test_case_du_formulaire_du_site(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("news_ajouter"), {"titre": "Souper annuel", "date": "2026-10-17", "a_la_une": "on"})
        news = NewsPage.objects.get(title="Souper annuel")
        self.assertTrue(news.a_la_une)

        reponse = self.client.get(reverse("news_modifier", args=[news.pk]))
        self.assertTrue(reponse.context["form"].initial["a_la_une"])

        self.client.post(reverse("news_modifier", args=[news.pk]), {"titre": "Souper annuel", "date": "2026-10-17"})
        news.refresh_from_db()
        self.assertFalse(news.a_la_une)


class EditeurBlocsTests(TestCase):
    """Éditeur par blocs du site : tous les champs de l'actualité, contenu
    enrichi, images positionnées."""

    def setUp(self):
        racine = Page.objects.get(depth=1)
        self.index = racine.add_child(instance=NewsIndexPage(title="Actualités", slug="actualites"))
        Site.objects.all().delete()
        Site.objects.create(hostname="testserver", root_page=self.index, is_default_site=True)
        Utilisateur = get_user_model()
        self.admin = Utilisateur.objects.create_user("admin", "admin@exemple.be", "mdp", is_staff=True)
        # Droit Wagtail de publier (groupe créé par les migrations de Wagtail)
        self.admin.groups.add(Group.objects.get(name="Moderators"))
        self.client.force_login(self.admin)

    def _publier(self, **champs):
        donnees = {"titre": "Spectacle", "date": "2026-10-17", "auteur": "Marie", "corps": _corps()}
        donnees.update(champs)
        return self.client.post(reverse("news_ajouter"), donnees)

    def test_tous_les_blocs_et_champs(self):
        photo = _image_wagtail()
        self._publier(
            mots_cles="théâtre, Blé qui Lève, Théâtre",
            corps=_corps(
                ("heading", "Au programme"),
                ("paragraph", '<p>Un <b>grand</b> <a href="https://exemple.be">spectacle</a>.</p>'),
                ("image_positionnee", {"image": photo.pk, "position": "gauche", "legende": "La troupe"}),
                ("quote", {"text": "Magnifique !", "attribution": "Un spectateur"}),
                ("callout", {"title": "Infos", "text": "<ul><li>20 h</li></ul>"}),
                ("useful_link", {"title": "Billetterie", "url": "https://billets.exemple.be"}),
            ),
        )
        news = NewsPage.objects.get(title="Spectacle")
        self.assertEqual(
            [bloc.block_type for bloc in news.body],
            ["heading", "paragraph", "image_positionnee", "quote", "callout", "useful_link"],
        )
        self.assertEqual(news.author, "Marie")
        self.assertEqual(sorted(t.name for t in news.tags.all()), ["Blé qui Lève", "théâtre"])
        self.assertEqual(news.body[2].value["position"], "gauche")

        page = self.client.get(news.url)
        self.assertContains(page, "image-positionnee--gauche")
        self.assertContains(page, "<figcaption>La troupe</figcaption>", html=True)
        self.assertContains(page, '<a href="https://exemple.be">spectacle</a>', html=True)

    def test_aller_retour_sans_perte(self):
        """Une actualité créée dans Wagtail, rouverte puis enregistrée telle
        quelle depuis le site, garde ses blocs (l'ancienne image devient une
        image positionnée en pleine largeur)."""
        photo = _image_wagtail()
        news = self.index.add_child(instance=NewsPage(title="Concert", slug="concert", date=date.today()))
        news.body = [
            ("paragraph", "<p>Texte <i>riche</i></p>"),
            ("image", photo),
            ("quote", {"text": "Bravo", "attribution": ""}),
        ]
        news.save_revision().publish()

        corps = self.client.get(reverse("news_modifier", args=[news.pk])).context["form"].initial["corps"]
        self.client.post(reverse("news_modifier", args=[news.pk]), {"titre": "Concert", "date": "2026-10-17", "corps": corps})

        news.refresh_from_db()
        self.assertEqual([b.block_type for b in news.body], ["paragraph", "image_positionnee", "quote"])
        self.assertEqual(news.body[0].value.source, "<p>Texte <i>riche</i></p>")
        self.assertEqual((news.body[1].value["image"], news.body[1].value["position"]), (photo, "pleine"))

    def test_texte_enrichi_nettoye(self):
        self._publier(corps=_corps(("paragraph", '<p onclick="x()">Ok<script>alert(1)</script> <a href="javascript:alert(1)">piège</a></p><img src=x onerror=alert(1)>')))
        news = NewsPage.objects.get(title="Spectacle")
        self.assertEqual(news.body[0].value.source, "<p>Ok piège</p>")

    def test_bloc_image_sans_photo_refuse(self):
        reponse = self._publier(corps=_corps(("image_positionnee", {"image": None, "position": "pleine", "legende": ""})))
        self.assertContains(reponse, "Un bloc image n&#x27;a pas de photo")
        self.assertFalse(NewsPage.objects.filter(title="Spectacle").exists())

    def test_envoi_de_photo(self):
        reponse = self.client.post(reverse("news_envoyer_photo"), {"photo": _photo("Ma_photo.png")})
        self.assertEqual(reponse.status_code, 200)
        image = Image.objects.get(pk=reponse.json()["id"])
        self.assertEqual(image.title, "Ma photo")
        self.assertTrue(reponse.json()["apercu"])

        faux = SimpleUploadedFile("faux.png", b"pas une image", content_type="image/png")
        self.assertEqual(self.client.post(reverse("news_envoyer_photo"), {"photo": faux}).status_code, 400)

        self.client.logout()
        self.assertEqual(self.client.post(reverse("news_envoyer_photo"), {"photo": _photo()}).status_code, 302)

    def test_retirer_l_image_mise_en_avant(self):
        self._publier(image=_photo())
        news = NewsPage.objects.get(title="Spectacle")
        self.assertIsNotNone(news.featured_image)

        self.client.post(reverse("news_modifier", args=[news.pk]), {
            "titre": "Spectacle", "date": "2026-10-17", "corps": _corps(), "retirer_image": "on",
        })
        news.refresh_from_db()
        self.assertIsNone(news.featured_image)


    def _ordre_affichage(self, *blocs):
        photo = _image_wagtail()
        news = self.index.add_child(instance=NewsPage(title="Ordre", slug=f"ordre-{NewsPage.objects.count()}", date=date.today()))
        news.body = [
            ("image_positionnee", {"image": photo, "position": bloc, "legende": ""}) if bloc in ("gauche", "droite", "pleine")
            else (bloc, "<p>Texte</p>" if bloc == "paragraph" else "Titre")
            for bloc in blocs
        ]
        return [b.value["position"] if b.block_type == "image_positionnee" else b.block_type for b in news.corps_affichage]

    def test_image_flottante_apres_le_texte_remontee(self):
        """Image à droite ajoutée après le dernier paragraphe : affichée avant
        lui, pour que le texte l'entoure (et non à côté du bandeau de partage)."""
        self.assertEqual(self._ordre_affichage("paragraph", "droite"), ["droite", "paragraph"])
        self.assertEqual(
            self._ordre_affichage("heading", "paragraph", "gauche", "droite", "heading"),
            ["heading", "gauche", "droite", "paragraph", "heading"],
        )

    def test_ordre_garde_si_texte_apres_ou_pleine_largeur(self):
        self.assertEqual(self._ordre_affichage("paragraph", "gauche", "paragraph"), ["paragraph", "gauche", "paragraph"])
        self.assertEqual(self._ordre_affichage("paragraph", "pleine"), ["paragraph", "pleine"])
        self.assertEqual(self._ordre_affichage("heading", "droite"), ["heading", "droite"])


class NettoyeurTexteEnrichiTests(TestCase):

    def test_conversions(self):
        cas = {
            "Texte libre": "<p>Texte libre</p>",
            "<div>Ligne<br>2</div><p><br></p>": "<p>Ligne<br/>2</p>",
            "<strong>G</strong> <em>I</em>": "<p><b>G</b> <i>I</i></p>",
            "<ul><li><p>un</p></li><li>deux</li></ul>": "<ul><li>un</li><li>deux</li></ul>",
            '<h1>Titre</h1><p><span style="color:red">rouge</span></p>': "<h2>Titre</h2><p>rouge</p>",
            '<p><a href="//pirate.example">x</a> &lt;b&gt;</p>': "<p>x &lt;b&gt;</p>",
        }
        for entree, attendu in cas.items():
            with self.subTest(entree=entree):
                self.assertEqual(nettoyer_texte_enrichi(entree), attendu)
