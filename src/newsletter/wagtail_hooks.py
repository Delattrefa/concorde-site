from django.urls import include, path

from wagtail import hooks
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from . import views_admin
from .models import Abonne, Newsletter


class NewsletterViewSet(SnippetViewSet):
    model = Newsletter
    icon = "mail"
    menu_label = "Newsletters"
    add_to_admin_menu = False
    list_display = ["titre", "objet", "statut", "date_modification", "lien_envoi"]
    list_filter = ["statut"]
    search_fields = ["titre", "objet"]
    search_backend_name = None          # recherche directe en base
    ordering = ["-date_creation"]
    copy_view_enabled = True            # « Dupliquer » pour repartir d'une lettre précédente


class AbonneViewSet(SnippetViewSet):
    model = Abonne
    icon = "user"
    menu_label = "Abonnés"
    add_to_admin_menu = False
    list_display = ["email", "prenom", "nom", "statut", "source", "date_inscription"]
    list_filter = ["statut", "source"]
    search_fields = ["email", "prenom", "nom"]
    search_backend_name = None
    ordering = ["-date_inscription"]
    list_per_page = 50
    copy_view_enabled = False
    inspect_view_enabled = True
    # Bouton « Télécharger » (CSV ou Excel) de la liste : respecte les filtres
    # et la recherche en cours.
    list_export = [
        "email", "prenom", "nom", "statut", "source",
        "date_inscription", "date_confirmation", "date_desinscription",
    ]
    export_headings = {
        "email": "Adresse e-mail", "prenom": "Prénom", "nom": "Nom", "statut": "Statut",
        "source": "Origine", "date_inscription": "Inscrit le",
        "date_confirmation": "Confirmé le", "date_desinscription": "Désinscrit le",
    }
    export_filename = "abonnes-newsletter"


class NewsletterGroup(SnippetViewSetGroup):
    items = (NewsletterViewSet, AbonneViewSet)
    menu_label = "Newsletter"
    menu_icon = "mail"
    menu_order = 250


register_snippet(NewsletterGroup)


@hooks.register("register_admin_urls")
def urls_envoi_newsletter():
    urls = [
        path("<int:pk>/envoyer/", views_admin.envoyer, name="envoyer"),
        path("<int:pk>/suivi/", views_admin.suivi, name="suivi"),
    ]
    return [path("newsletter/", include((urls, "newsletter_admin")))]
