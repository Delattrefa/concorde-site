"""
Réglages communs à tous les environnements (dev / production).
Projet : Site vitrine ASBL "La Concorde" (théâtre / activités culturelles)
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# -----------------------------------------------------------------------
# Applications
# -----------------------------------------------------------------------
INSTALLED_APPS = [
    # Applications propres au site
    "home",
    "news",
    "media_gallery",
    "info",
    "contact",
    "search",
    "navigation",
    "calendrier",
    "theatre",
    "page_libre",
    "consentement",

    # Wagtail
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.settings",
    "wagtail.contrib.search_promotions",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",

    # Référencement (SEO) : ajoute les champs meta/Open Graph/Twitter/données
    # structurées sur les pages, et un panneau "SEO" dans les paramètres du
    # site (organisation, réseaux sociaux, image de partage par défaut...).
    "wagtailseo",
    "wagtail",
    "wagtail.locales",

    "modelcluster",
    "taggit",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "django.contrib.sitemaps",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    # Bloque les contenus de sites tiers (cartes, vidéos) avant consentement
    "consentement.middleware.BlocageContenusTiersMiddleware",
]

ROOT_URLCONF = "concorde_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wagtail.contrib.settings.context_processors.settings",
                "navigation.context_processors.menus",
            ],
        },
    }
]

WSGI_APPLICATION = "concorde_site.wsgi.application"

# -----------------------------------------------------------------------
# Base de données (surchargée en dev/production)
# -----------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# -----------------------------------------------------------------------
# Internationalisation — site francophone (Belgique)
# -----------------------------------------------------------------------
LANGUAGE_CODE = "fr-be"
TIME_ZONE = "Europe/Brussels"
USE_I18N = True
USE_TZ = True

# La semaine commence un lundi (convention belge/française), utilisé
# notamment par l'application 'calendrier' et les widgets de date.
FIRST_DAY_OF_WEEK = 1  # 0 = dimanche, 1 = lundi

# Formats d'affichage des dates/heures en français de Belgique
# (ex : 21/09/2026, 21 septembre 2026, 14:30).
DATE_FORMAT = "j F Y"
SHORT_DATE_FORMAT = "d/m/Y"
DATETIME_FORMAT = "j F Y, H:i"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
TIME_FORMAT = "H:i"
DATE_INPUT_FORMATS = ["%d/%m/%Y", "%Y-%m-%d"]

WAGTAIL_CONTENT_LANGUAGES = LANGUAGES = [
    ("fr", "Français"),
]
WAGTAIL_I18N_ENABLED = False

# -----------------------------------------------------------------------
# Fichiers statiques / médias
# -----------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# -----------------------------------------------------------------------
# Wagtail
# -----------------------------------------------------------------------
WAGTAIL_SITE_NAME = "La Concorde asbl"
WAGTAILADMIN_BASE_URL = "http://localhost:8000"

WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
    }
}

# Nombre de résultats par page sur /recherche/
SEARCH_RESULTS_PER_PAGE = 10

# -----------------------------------------------------------------------
# Authentification (utilisée notamment par l'application 'calendrier' :
# connexion nécessaire pour ajouter une activité, réservée aux membres).
# -----------------------------------------------------------------------
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "calendrier:mois_courant"
LOGOUT_REDIRECT_URL = "calendrier:mois_courant"
