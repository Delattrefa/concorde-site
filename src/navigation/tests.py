"""
Tests du menu principal : sous-menus déroulants et sous-menu « Théâtre ».

Lancement : python manage.py test navigation
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import MainMenu, MainMenuItem


class MenuPrincipalTests(TestCase):
    def setUp(self):
        self.menu = MainMenu.objects.create()

    def _page(self):
        return self.client.get(reverse("search"))

    def test_element_sans_sous_menu_reste_un_simple_lien(self):
        MainMenuItem.objects.create(menu=self.menu, link_title="Contact", link_url="/contact/")

        reponse = self._page()

        self.assertContains(reponse, '<li class="main-nav__item"><a href="/contact/">Contact</a></li>', html=True)
        self.assertNotContains(reponse, "sous-menu-1")

    def test_element_avec_sous_menu(self):
        MainMenuItem.objects.create(
            menu=self.menu, link_title="Infos", link_url="/infos/",
            sous_menu=[
                ("lien", {"titre": "Accès", "url": "/infos/acces/"}),
                ("lien", {"titre": "Partenaire", "url": "https://exemple.be", "ouvrir_nouvel_onglet": True}),
            ],
        )

        reponse = self._page()

        self.assertContains(reponse, 'aria-controls="sous-menu-1"')
        self.assertContains(reponse, '<a href="/infos/">Infos</a>', html=True)
        self.assertContains(reponse, '<a href="/infos/acces/">Accès</a>', html=True)
        self.assertContains(
            reponse, '<a href="https://exemple.be" target="_blank" rel="noopener">Partenaire</a>', html=True
        )

    def test_element_sans_lien_ouvre_seulement_son_sous_menu(self):
        MainMenuItem.objects.create(
            menu=self.menu, link_title="Association",
            sous_menu=[("lien", {"titre": "Historique", "url": "/historique/"})],
        )

        reponse = self._page()

        self.assertContains(reponse, "main-nav__deplier--titre")
        self.assertContains(reponse, '<a href="/historique/">Historique</a>', html=True)

    def test_sous_menu_theatre_masque_sans_permission(self):
        self.client.force_login(get_user_model().objects.create_user("membre", password="mdp"))

        reponse = self._page()

        self.assertNotContains(reponse, "sous-menu-theatre")

    def test_sous_menu_theatre_avec_permission(self):
        utilisateur = get_user_model().objects.create_user("regie", password="mdp")
        utilisateur.user_permissions.add(Permission.objects.get(codename="acces_application"))
        self.client.force_login(utilisateur)

        reponse = self._page()

        self.assertContains(reponse, 'id="sous-menu-theatre"')
        self.assertContains(reponse, f'<a href="{reverse("representation_list")}">Représentations</a>', html=True)
        self.assertContains(reponse, f'<a href="{reverse("reservation_list")}">Réservations</a>', html=True)

    def test_page_du_theatre_dans_la_charte_du_site(self):
        self.client.force_login(
            get_user_model().objects.create_superuser("admin", "admin@exemple.be", "mdp")
        )

        reponse = self.client.get(reverse("reservation_list"))

        # En-tête du site, lien de la page courante signalé dans le sous-menu
        self.assertContains(reponse, 'class="site-header"')
        self.assertContains(reponse, 'class="theatre-app"')
        self.assertContains(
            reponse, f'<a href="{reverse("reservation_list")}" aria-current="page">Réservations</a>', html=True
        )
