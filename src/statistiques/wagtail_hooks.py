from django.contrib.auth.models import Permission
from django.urls import path, reverse

from wagtail import hooks
from wagtail.admin.menu import MenuItem

from . import views


class MenuStatistiques(MenuItem):
    def is_shown(self, request):
        return views.peut_consulter(request.user)


@hooks.register("register_admin_urls")
def urls_statistiques():
    return [path("statistiques/", views.tableau, name="statistiques")]


@hooks.register("register_admin_menu_item")
def menu_statistiques():
    return MenuStatistiques("Statistiques", reverse("statistiques"), icon_name="table", order=260)


@hooks.register("register_permissions")
def permission_statistiques():
    # Cochable dans Paramètres → Groupes, pour l'accorder à d'autres que
    # les super-utilisateurs
    return Permission.objects.filter(content_type__app_label="statistiques", codename="consulter_statistiques")
