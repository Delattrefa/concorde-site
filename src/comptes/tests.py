"""
Tests des invitations : envoi réservé aux super-utilisateurs, lien à usage
unique et limité dans le temps, compte de simple membre, connexion par
e-mail.

Lancement : python manage.py test comptes
"""
import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import InvitationMembre

Membre = get_user_model()
MOT_DE_PASSE = "Bénévole-Concorde-2026"


class InvitationTests(TestCase):
    def setUp(self):
        self.chef = Membre.objects.create_superuser("chef", "chef@exemple.be", "mdp", first_name="Claire", last_name="Dumont")
        self.ajout = reverse("admin:comptes_invitationmembre_add")

    def inviter(self, email="nouveau@exemple.be", **champs):
        self.client.force_login(self.chef)
        self.client.post(self.ajout, {"email": email, "prenom": "Léa", "nom": "Van den Berg",
                                      "message": "On compte sur toi au bar !", **champs})
        self.client.logout()
        return re.search(r"https?://\S+/inscription/[\w-]+/", mail.outbox[-1].body).group(0)

    def chemin(self, lien):
        """Adresse relative du lien reçu par e-mail."""
        return "/" + lien.split("://", 1)[1].split("/", 1)[1]

    def inscrire(self, lien, **champs):
        donnees = {"prenom": "Léa", "nom": "Van den Berg", "email": "nouveau@exemple.be",
                   "mot_de_passe": MOT_DE_PASSE, "confirmation": MOT_DE_PASSE, **champs}
        return self.client.post(self.chemin(lien), donnees)

    def test_parcours_complet(self):
        lien = self.inviter()
        email = mail.outbox[-1]
        self.assertEqual(email.to, ["nouveau@exemple.be"])
        self.assertIn("Claire Dumont vous invite", email.body)
        self.assertIn("On compte sur toi au bar", email.body)
        self.assertIn(lien, email.alternatives[0][0])
        # Seule l'empreinte du lien est en base
        jeton = lien.rstrip("/").rsplit("/", 1)[1]
        self.assertFalse(InvitationMembre.objects.filter(jeton_hache=jeton).exists())

        reponse = self.client.get(self.chemin(lien))
        self.assertContains(reponse, 'value="nouveau@exemple.be"')
        reponse = self.inscrire(lien)
        self.assertRedirects(reponse, reverse("planning:accueil"))

        membre = Membre.objects.get(email="nouveau@exemple.be")
        self.assertEqual((membre.username, membre.first_name, membre.last_name), ("lea.van-den-berg", "Léa", "Van den Berg"))
        self.assertFalse(membre.is_staff or membre.is_superuser)
        self.assertFalse(membre.groups.exists() or membre.user_permissions.exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), membre.pk)  # connecté d'office
        invitation = InvitationMembre.objects.get()
        self.assertEqual((invitation.statut, invitation.membre), (InvitationMembre.ACCEPTEE, membre))
        self.assertIn("a rejoint l'espace des membres", mail.outbox[-1].subject)  # l'inviteur est prévenu

        # Le lien ne sert qu'une fois
        self.client.logout()
        reponse = self.client.get(self.chemin(lien))
        self.assertEqual(reponse.status_code, 410)
        self.assertContains(reponse, "Compte déjà créé", status_code=410)

    def test_connexion_par_email_ou_identifiant(self):
        self.inscrire(self.inviter())
        self.client.logout()
        for identifiant in ("Nouveau@Exemple.be", "lea.van-den-berg"):
            self.client.post(reverse("login"), {"username": identifiant, "password": MOT_DE_PASSE})
            self.assertIn("_auth_user_id", self.client.session, identifiant)
            self.client.logout()
        self.client.post(reverse("login"), {"username": "nouveau@exemple.be", "password": "mauvais"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_reserve_aux_super_utilisateurs(self):
        equipe = Membre.objects.create_user("equipe", "e@exemple.be", "mdp", is_staff=True)
        self.client.force_login(equipe)
        self.assertEqual(self.client.get(self.ajout).status_code, 403)
        self.assertNotContains(self.client.get(reverse("admin:index")), "Invitations de membres")

    def test_lien_inconnu_expire_ou_annule(self):
        self.assertEqual(self.client.get("/inscription/inexistant/").status_code, 404)
        lien = self.inviter()
        InvitationMembre.objects.update(expire_le=timezone.now() - timedelta(minutes=1))
        self.assertContains(self.client.get(self.chemin(lien)), "a expiré ou a été annulé", status_code=410)
        self.assertEqual(self.inscrire(lien).status_code, 410)
        self.assertFalse(Membre.objects.filter(email="nouveau@exemple.be").exists())

    def test_renvoyer_cree_un_nouveau_lien(self):
        ancien = self.inviter()
        InvitationMembre.objects.update(expire_le=timezone.now() - timedelta(days=1))
        self.client.force_login(self.chef)
        invitation = InvitationMembre.objects.get()
        self.client.post(reverse("admin:comptes_invitationmembre_changelist"),
                         {"action": "renvoyer", "_selected_action": [invitation.pk]})
        nouveau = re.search(r"https?://\S+/inscription/[\w-]+/", mail.outbox[-1].body).group(0)
        self.assertNotEqual(ancien, nouveau)
        self.client.logout()
        self.assertEqual(self.client.get(self.chemin(ancien)).status_code, 404)
        self.assertEqual(self.client.get(self.chemin(nouveau)).status_code, 200)

    def test_adresse_deja_utilisee_ou_deja_invitee(self):
        self.client.force_login(self.chef)
        reponse = self.client.post(self.ajout, {"email": "CHEF@exemple.be"})
        self.assertContains(reponse, "Un compte existe déjà")
        self.inviter()
        self.client.force_login(self.chef)
        reponse = self.client.post(self.ajout, {"email": "nouveau@exemple.be"})
        self.assertContains(reponse, "déjà en attente")
        self.assertEqual(InvitationMembre.objects.count(), 1)

    def test_mot_de_passe_controle(self):
        lien = self.inviter()
        reponse = self.inscrire(lien, mot_de_passe="court", confirmation="court")
        self.assertContains(reponse, "trop court")
        reponse = self.inscrire(lien, confirmation="autre-chose-123")
        self.assertContains(reponse, "pas identiques")
        self.assertFalse(Membre.objects.filter(email="nouveau@exemple.be").exists())

    def test_identifiant_rendu_unique(self):
        Membre.objects.create_user("lea.van-den-berg", "autre@exemple.be", "mdp")
        self.inscrire(self.inviter())
        self.assertTrue(Membre.objects.filter(username="lea.van-den-berg2", email="nouveau@exemple.be").exists())

    def test_erreur_smtp_affiche_le_lien(self):
        self.client.force_login(self.chef)
        with self.settings(EMAIL_BACKEND="comptes.tests.BoiteEnPanne"):
            reponse = self.client.post(self.ajout, {"email": "nouveau@exemple.be"}, follow=True)
        self.assertContains(reponse, "Transmettez-lui vous-même ce lien personnel")
        self.assertIsNone(InvitationMembre.objects.get().envoyee_le)


class BoiteEnPanne:
    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise ConnectionError("serveur SMTP injoignable")
