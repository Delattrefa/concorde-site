"""
Tests des actualités proposées depuis le site : publication immédiate pour
les administrateurs, validation (circuit Wagtail « Moderators approval »)
pour les autres membres, droits de l'auteur.

Lancement : python manage.py test news
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from wagtail.models import Page, Site, WorkflowPage, WorkflowState

from .models import NewsIndexPage, NewsPage


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ValidationActualitesTests(TestCase):

    def setUp(self):
        Utilisateur = get_user_model()
        self.membre = Utilisateur.objects.create_user("membre", "membre@exemple.be", "mdp")
        self.autre_membre = Utilisateur.objects.create_user("autre", "autre@exemple.be", "mdp")
        self.admin = Utilisateur.objects.create_user("admin", "admin@exemple.be", "mdp", is_staff=True)
        self.superadmin = Utilisateur.objects.create_superuser("super", "super@exemple.be", "mdp")

        racine = Page.objects.get(depth=1)
        self.index = racine.add_child(instance=NewsIndexPage(title="Actualités", slug="actualites"))
        Site.objects.all().delete()
        Site.objects.create(hostname="testserver", root_page=self.index, is_default_site=True)

    # ── Outils ────────────────────────────────────────────────────────────

    def _proposer(self, utilisateur, titre="Fête du village"):
        self.client.force_login(utilisateur)
        reponse = self.client.post(reverse("news_ajouter"), {
            "titre": titre, "intro": "Résumé", "contenu": "Texte de l'actualité.",
        })
        return reponse, NewsPage.objects.get(draft_title=titre)

    def _modifier(self, news, titre):
        return self.client.post(reverse("news_modifier", args=[news.pk]), {
            "titre": titre, "intro": "Résumé modifié", "contenu": "Nouveau texte.",
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
