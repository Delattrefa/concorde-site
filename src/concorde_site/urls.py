from django.conf import settings
from django.urls import include, path
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.templatetags.static import static as url_statique

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from search import views as search_views
from news import views as news_views
from media_gallery import views as media_gallery_views

def favicon_ico(request):
    """Certains navigateurs et robots demandent /favicon.ico directement."""
    return redirect(url_statique("img/favicon.ico"))


urlpatterns = [
    path("favicon.ico", favicon_ico),
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("recherche/", search_views.search, name="search"),

    # Application 'calendrier' : activités + réservations de salle
    path("calendrier/", include("calendrier.urls", namespace="calendrier")),

    # Application 'theatre' : gestion des places de théâtre (site secondaire,
    # intégrée telle quelle depuis son propre projet Django d'origine).
    # Volontairement SANS namespace : ses propres templates utilisent des
    # noms d'URL globaux (ex : {% url 'representation_list' %}) hérités de
    # ce projet d'origine ; les renommer en 'theatre:xxx' obligerait à
    # modifier chacun de ses templates. Aucune collision avec les noms
    # d'URL des autres apps du site (vérifié).
    # Authentification : réutilise le système de connexion du site
    # principal (@login_required renvoie vers settings.LOGIN_URL, déjà
    # configuré plus bas) — pas de compte ni de page de connexion séparée.
    # ⚠️ Ce préfixe rend inaccessible toute page Wagtail qui aurait le
    # même chemin ("theatre/...") : ne pas créer de page avec ce slug.
    path("theatre/", include("theatre.urls")),

    # CRUD des actualités depuis le site (utilisateurs connectés).
    # Volontairement hors de l'arborescence Wagtail ("actualites/" est le
    # chemin de la page Wagtail elle-même, géré par wagtail_urls plus bas) :
    # ces chemins distincts évitent tout conflit avec le routage des pages.
    path("ajouter-actualite/", news_views.ajouter_news, name="news_ajouter"),
    path("modifier-actualite/<int:pk>/", news_views.modifier_news, name="news_modifier"),
    path("supprimer-actualite/<int:pk>/", news_views.supprimer_news, name="news_supprimer"),

    # Ajout de plusieurs photos à la fois dans un album (administrateurs).
    # Même logique de chemin distinct de l'arborescence Wagtail que ci-dessus.
    path("galerie/<int:album_id>/ajouter-photos/", media_gallery_views.ajouter_photos, name="galerie_ajouter_photos"),

    # Connexion / déconnexion (nécessaires pour ajouter une activité).
    # Utilise les vues d'authentification standard de Django avec nos
    # propres gabarits (voir templates/registration/).
    path("connexion/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    try:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

elif getattr(settings, "SERVE_MEDIA", False):
    # Production (o2switch) : solution de secours si Apache ne sert pas
    # directement le dossier /media/ (activée par SERVE_MEDIA=1 dans .env).
    # Les contrats de location sont exclus : ils ne sont accessibles qu'aux
    # administrateurs, via calendrier:reservation_contrat_pdf.
    from django.urls import re_path
    from django.views.static import serve

    urlpatterns += [
        re_path(
            r"^media/(?!contrats_location/)(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]


# Laisser Wagtail gérer toutes les pages non capturées ci-dessus
# (accueil, médias, calendrier, infos, contact, ...)
urlpatterns += [
    path("", include(wagtail_urls)),
]
