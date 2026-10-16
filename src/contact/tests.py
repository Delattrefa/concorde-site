"""
Tests du formulaire de contact : protection anti-spam (champ piège et
limite par adresse IP), adresse de réponse des notifications et
destinataire obligatoire dans l'admin.

Lancement : python manage.py test contact
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings

from wagtail.contrib.forms.models import FormSubmission
from wagtail.models import Page, Site

from .models import LIMITE_MESSAGES_PAR_IP, ContactFormField, ContactPage


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ContactAntispamTests(TestCase):
    def setUp(self):
        cache.clear()
        racine = Page.objects.get(depth=1)
        self.page = racine.add_child(instance=ContactPage(
            title="Contact", slug="contact-test",
            to_address="infos@exemple.be", from_address="site@exemple.be", subject="Message du site",
        ))
        ContactFormField.objects.create(page=self.page, label="Message", field_type="multiline", required=True)
        Site.objects.all().delete()
        Site.objects.create(hostname="testserver", root_page=self.page, is_default_site=True)

    def _envoyer(self, entetes=None, **champs):
        donnees = {"message": "Bonjour, une question sur la salle."}
        donnees.update(champs)
        return self.client.post(self.page.url, donnees, REMOTE_ADDR="192.0.2.1", **(entetes or {}))

    def test_message_normal_enregistre_et_envoye(self):
        reponse = self._envoyer()
        self.assertContains(reponse, "Merci")
        self.assertEqual(FormSubmission.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_champ_piege_rempli_rien_envoye_mais_reponse_normale(self):
        reponse = self._envoyer(website="https://spam.example")
        self.assertContains(reponse, "Merci")
        self.assertEqual(FormSubmission.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_limite_par_ip(self):
        for _ in range(LIMITE_MESSAGES_PAR_IP):
            self._envoyer()

        reponse = self._envoyer(entetes={"HTTP_X_FORWARDED_FOR": "10.9.9.9"})
        self.assertContains(reponse, "Trop de messages")
        self.assertEqual(FormSubmission.objects.count(), LIMITE_MESSAGES_PAR_IP)
        self.assertEqual(len(mail.outbox), LIMITE_MESSAGES_PAR_IP)

    def test_erreurs_de_saisie_non_comptees(self):
        for _ in range(LIMITE_MESSAGES_PAR_IP + 2):
            self._envoyer(message="")

        self.assertContains(self._envoyer(), "Merci")

    def test_formulaire_contient_le_champ_piege(self):
        self.assertContains(self.client.get(self.page.url), 'name="website"')

    def test_repondre_ecrit_au_visiteur(self):
        ContactFormField.objects.create(page=self.page, label="Adresse mail", field_type="email", required=False)

        self._envoyer(adresse_mail="visiteur@exemple.be")

        self.assertEqual(mail.outbox[0].from_email, "site@exemple.be")
        self.assertEqual(mail.outbox[0].to, ["infos@exemple.be"])
        self.assertEqual(mail.outbox[0].reply_to, ["visiteur@exemple.be"])

    def test_sans_adresse_du_visiteur_pas_d_adresse_de_reponse(self):
        self._envoyer()
        self.assertEqual(mail.outbox[0].reply_to, [])


class DestinataireObligatoireTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("secretariat", "s@exemple.be", "Un-bon-mot-de-passe")
        self.client.force_login(self.admin)
        self.racine = Page.objects.get(depth=1)
        self.page = self.racine.add_child(instance=ContactPage(title="Contact", slug="contact-test"))

    def _modifier(self, action, to_address):
        donnees = {
            "title": "Contact", "slug": "contact-test", "to_address": to_address,
            "from_address": "site@exemple.be", "subject": "Message du site",
            "form_fields-TOTAL_FORMS": "0", "form_fields-INITIAL_FORMS": "0",
            "form_fields-MIN_NUM_FORMS": "0", "form_fields-MAX_NUM_FORMS": "1000",
        }
        if action == "publier":
            donnees["action-publish"] = "action-publish"
        return self.client.post(f"/admin/pages/{self.page.pk}/edit/", donnees)

    def test_publication_refusee_sans_destinataire(self):
        reponse = self._modifier("publier", "")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("to_address", reponse.context["form"].errors)
        self.page.refresh_from_db()
        self.assertEqual(self.page.to_address, "")

    def test_brouillon_accepte_sans_destinataire(self):
        self.assertEqual(self._modifier("brouillon", "").status_code, 302)

    def test_publication_avec_destinataire(self):
        self.assertEqual(self._modifier("publier", "infos@exemple.be").status_code, 302)
        self.page.refresh_from_db()
        self.assertEqual(self.page.to_address, "infos@exemple.be")
