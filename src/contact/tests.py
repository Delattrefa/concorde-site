"""
Tests du formulaire de contact : protection anti-spam (champ piège et
limite par adresse IP).

Lancement : python manage.py test contact
"""
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings

from wagtail.contrib.forms.models import FormSubmission
from wagtail.models import Page, Site

from .models import LIMITE_MESSAGES_PAR_IP, ContactFormField, ContactPage


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    STORAGES={"staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
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
