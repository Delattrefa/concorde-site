"""
Tests des statistiques de fréquentation : ce qui est compté (ou non),
visiteurs distincts sans conserver d'adresse IP, purge, et accès au
tableau de bord réservé.

Lancement : python manage.py test statistiques
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.http import HttpResponse, HttpResponseNotFound
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from . import mesure
from .middleware import MesureAudienceMiddleware
from .models import EmpreinteDuJour, Jour, PageJour, ProvenanceJour, SelDuJour

NAVIGATEUR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
MOBILE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"


class MesureTests(TestCase):
    def setUp(self):
        mesure._sel = None
        self.addCleanup(setattr, mesure, "_sel", None)
        self.reponse = HttpResponse("<html></html>")
        self.middleware = MesureAudienceMiddleware(lambda request: self.reponse)

    def visiter(self, chemin="/", navigateur=NAVIGATEUR, ip="198.51.100.7", utilisateur=None, **entetes):
        requete = RequestFactory().get(chemin, HTTP_USER_AGENT=navigateur, REMOTE_ADDR=ip, **entetes)
        requete.user = utilisateur or AnonymousUser()
        self.middleware(requete)

    def jour(self):
        return Jour.objects.get(date=timezone.localdate())

    def test_visiteurs_distincts_et_pages_vues(self):
        self.visiter("/")
        self.visiter("/news/")
        self.visiter("/news/", ip="203.0.113.9", navigateur=MOBILE)
        jour = self.jour()
        self.assertEqual((jour.vues, jour.visiteurs, jour.vues_mobiles), (3, 2, 1))
        self.assertEqual(PageJour.objects.get(chemin="/news/").vues, 2)

    def test_aucune_adresse_ip_conservee(self):
        self.visiter(ip="198.51.100.7")
        empreinte = EmpreinteDuJour.objects.get().empreinte
        self.assertEqual(len(empreinte), 64)
        self.assertNotIn("198.51.100.7", empreinte)

    def test_ne_sont_pas_comptes(self):
        equipe = get_user_model().objects.create_user("equipe", "e@exemple.be", "mdp", is_staff=True)
        self.visiter(navigateur="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
        self.visiter(navigateur="")
        self.visiter("/admin/pages/")
        self.visiter("/media/images/photo.jpg")
        self.visiter(utilisateur=equipe)
        self.visiter(HTTP_SEC_PURPOSE="prefetch")
        self.reponse = HttpResponseNotFound("<html></html>")
        self.visiter("/page-inexistante/")
        self.assertFalse(Jour.objects.exists())

    def test_membre_connecte_compte(self):
        membre = get_user_model().objects.create_user("membre", "m@exemple.be", "mdp")
        self.visiter(utilisateur=membre)
        self.assertEqual(self.jour().vues, 1)

    def test_provenance(self):
        self.visiter(HTTP_REFERER="https://www.google.be/")
        self.visiter(HTTP_REFERER="https://lm.facebook.com/l.php?u=x")
        self.visiter(HTTP_REFERER="https://www.honnelles.be/agenda/")
        self.visiter(HTTP_REFERER="http://testserver/news/")  # navigation interne
        self.assertEqual(
            dict(ProvenanceJour.objects.values_list("source", "vues")),
            {"Google": 1, "Facebook": 1, "honnelles.be": 1},
        )

    def test_purge_du_lendemain(self):
        hier = timezone.localdate() - timedelta(days=1)
        SelDuJour.objects.create(date=hier, sel="x")
        EmpreinteDuJour.objects.create(date=hier, empreinte="y")
        tres_ancien = timezone.localdate() - timedelta(days=800)
        Jour.objects.create(date=tres_ancien, vues=5)
        Jour.objects.create(date=hier, vues=5)
        self.visiter()
        self.assertEqual(list(SelDuJour.objects.values_list("date", flat=True)), [timezone.localdate()])
        self.assertFalse(EmpreinteDuJour.objects.filter(date=hier).exists())
        self.assertEqual(sorted(Jour.objects.values_list("date", flat=True)), [hier, timezone.localdate()])

    def test_erreur_de_mesure_sans_consequence(self):
        requete = RequestFactory().get("/", HTTP_USER_AGENT=NAVIGATEUR)
        requete.user = AnonymousUser()
        with self.assertLogs("statistiques.mesure", level="ERROR"), \
                self.settings(STATISTIQUES_CONSERVATION_JOURS=None):  # fait échouer la purge
            reponse = self.middleware(requete)
        self.assertEqual(reponse.status_code, 200)


class TableauTests(TestCase):
    def setUp(self):
        self.url = reverse("statistiques")
        aujourdhui = timezone.localdate()
        Jour.objects.create(date=aujourdhui, vues=12, visiteurs=5, vues_mobiles=6)
        Jour.objects.create(date=aujourdhui - timedelta(days=40), vues=4, visiteurs=2)
        PageJour.objects.create(date=aujourdhui, chemin="/news/", vues=8)
        ProvenanceJour.objects.create(date=aujourdhui, source="Facebook", vues=3)

    def test_super_utilisateur(self):
        self.client.force_login(get_user_model().objects.create_superuser("admin", "a@exemple.be", "mdp"))
        reponse = self.client.get(self.url)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["totaux"]["visiteurs"], 5)
        self.assertEqual(reponse.context["part_mobile"], 50)
        self.assertEqual(len(reponse.context["barres"]), 30)
        self.assertContains(reponse, "Facebook")
        self.assertContains(reponse, "/news/")

        reponse = self.client.get(self.url, {"periode": "365"})
        self.assertEqual(reponse.context["totaux"]["visiteurs"], 7)
        self.assertTrue(reponse.context["par_mois"])
        self.assertIn(len(reponse.context["barres"]), (12, 13))

    def test_reserve_aux_admins(self):
        editeur = get_user_model().objects.create_user("editeur", "e@exemple.be", "mdp", is_staff=True)
        editeur.groups.add(Group.objects.get(name="Moderators"))
        self.client.force_login(editeur)
        self.assertNotEqual(self.client.get(self.url).status_code, 200)
        self.assertNotContains(self.client.get(reverse("wagtailadmin_home")), self.url)

        # Permission accordée à un groupe (Paramètres → Groupes)
        groupe = Group.objects.create(name="Statistiques")
        groupe.permissions.add(Permission.objects.get(codename="consulter_statistiques"))
        editeur.groups.add(groupe)
        editeur = get_user_model().objects.get(pk=editeur.pk)  # vide le cache des permissions
        self.client.force_login(editeur)
        self.assertEqual(self.client.get(self.url).status_code, 200)
