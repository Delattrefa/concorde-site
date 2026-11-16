"""
Réponse au demandeur depuis la fiche d'une réservation : e-mail envoyé par
le site, pièces jointes, contrat joint, copie et historique.

Lancement : python manage.py test calendrier.test_reponse
"""
import tempfile
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ContratLocation, MessageReservation, Reservation


class ReponseDemandeurTests(TestCase):
    def setUp(self):
        self.enterContext(override_settings(MEDIA_ROOT=self.enterContext(tempfile.TemporaryDirectory())))
        Utilisateur = get_user_model()
        self.admin = Utilisateur.objects.create_user(
            "admin", "marie@la-concorde.be", "mdp", is_staff=True, first_name="Marie", last_name="Dupont",
        )
        self.membre = Utilisateur.objects.create_user("membre", "membre@exemple.be", "mdp")
        self.reservation = Reservation.objects.create(
            nom="Durand", prenom="Luc", adresse="Rue Haute 5, 7387 Angre", email="luc.durand@exemple.be",
            telephone="0470 00 00 00", date_debut=date.today() + timedelta(days=30),
            date_fin=date.today() + timedelta(days=30),
        )
        self.url = reverse("calendrier:reservation_repondre", args=[self.reservation.pk])
        self.client.force_login(self.admin)

    def envoyer(self, **donnees):
        valeurs = {"objet": "Votre location", "message": "Bonjour,\nC'est d'accord.", "copie": "on"}
        valeurs.update(donnees)
        return self.client.post(self.url, valeurs)

    def test_reserve_aux_administrateurs(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.membre)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.post(self.url, {"objet": "x", "message": "y"}).status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_formulaire_pre_rempli(self):
        reponse = self.client.get(self.url)
        initial = reponse.context["form"].initial
        self.assertIn("votre demande de réservation de la salle le", initial["objet"])
        self.assertTrue(initial["message"].startswith("Bonjour Luc Durand,"))
        self.assertIn("Marie Dupont", initial["message"])
        self.assertNotIn("joindre_contrat", reponse.context["form"].fields)  # pas encore de contrat

    def test_envoi_avec_pieces_jointes_copie_et_historique(self):
        reponse = self.envoyer(pieces_jointes=[
            SimpleUploadedFile("plan d'accès.pdf", b"%PDF plan", content_type="application/pdf"),
            SimpleUploadedFile("salle.jpg", b"image", content_type="image/jpeg"),
        ])
        self.assertRedirects(reponse, reverse("calendrier:reservation_detail", args=[self.reservation.pk]) + "#messages")
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual((email.to, email.bcc, email.subject), (["luc.durand@exemple.be"], ["marie@la-concorde.be"], "Votre location"))
        self.assertEqual([a[0] for a in email.attachments], ["plan d'accès.pdf", "salle.jpg"])

        message = MessageReservation.objects.get()
        self.assertEqual((message.envoye_par, message.destinataire), (self.admin, "luc.durand@exemple.be"))
        self.assertEqual(message.liste_pieces_jointes(), ["plan d'accès.pdf", "salle.jpg"])
        fiche = self.client.get(reverse("calendrier:reservation_detail", args=[self.reservation.pk]))
        self.assertContains(fiche, "Messages envoyés au demandeur")
        self.assertContains(fiche, "C&#x27;est d&#x27;accord.")

    def test_sans_copie(self):
        self.envoyer(copie="")
        self.assertEqual(mail.outbox[0].bcc, [])

    def test_contrat_joint(self):
        contrat = ContratLocation.objects.create(
            reservation=self.reservation, delegue_prenom="Marie", delegue_nom="Dupont",
            montant_location=350, montant_caution=150,
        )
        contrat.fichier_pdf.save("contrat-durand.pdf", ContentFile(b"%PDF contrat"))
        self.assertIn("joindre_contrat", self.client.get(self.url).context["form"].fields)
        self.envoyer(joindre_contrat="on")
        self.assertEqual(mail.outbox[0].attachments[0][0], "contrat-durand.pdf")
        self.assertEqual(mail.outbox[0].attachments[0][1], b"%PDF contrat")

    def test_fichier_refuse(self):
        reponse = self.envoyer(pieces_jointes=[SimpleUploadedFile("virus.exe", b"MZ")])
        self.assertContains(reponse, "Type de fichier non accepté : virus.exe")
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(MessageReservation.objects.exists())

    def test_trop_lourd(self):
        with mock.patch("calendrier.forms.TAILLE_MAX_PIECES_JOINTES", 10):
            reponse = self.envoyer(pieces_jointes=[SimpleUploadedFile("gros.pdf", b"x" * 20)])
        self.assertContains(reponse, "Pièces jointes trop lourdes")
        self.assertEqual(len(mail.outbox), 0)

    def test_echec_d_envoi_rien_dans_l_historique(self):
        with mock.patch("calendrier.views.EmailMessage.send", side_effect=OSError("SMTP indisponible")), \
                self.assertLogs("calendrier.views", level="ERROR"):
            reponse = self.envoyer()
        self.assertContains(reponse, "n&#x27;a pas pu partir")
        self.assertFalse(MessageReservation.objects.exists())
