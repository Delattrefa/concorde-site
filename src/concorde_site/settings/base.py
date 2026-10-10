"""
Réglages communs à tous les environnements (dev / production).
Projet : Site vitrine ASBL "La Concorde" (théâtre / activités culturelles)
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Variables d'environnement du fichier src/.env (s'il existe). Chargé ici
# pour que les réglages ci-dessous (e-mail notamment) les voient, en
# développement comme en production.
load_dotenv(BASE_DIR / ".env")

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
    "newsletter",

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
# Cache
# Partagé sur disque entre tous les processus (Passenger en lance plusieurs,
# plus la tâche cron) : le cache mémoire par défaut est propre à chaque
# processus, ce qui rendait inopérante la limite d'inscriptions par IP de
# la newsletter. o2switch ne propose ni Redis ni Memcached.
# -----------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / "tmp" / "cache",
    }
}

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


# -----------------------------------------------------------------------
# E-mails (SMTP o2switch)
# Valeurs lues dans src/.env (voir .env.example). Sans EMAIL_HOST, les
# e-mails sont affichés dans la console au lieu d'être envoyés : pratique
# en développement, aucun risque d'écrire à de vrais abonnés.
# -----------------------------------------------------------------------
def _env_bool(nom, defaut=False):
    return os.environ.get(nom, str(defaut)).strip().lower() in ("1", "true", "yes", "oui", "on")


EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "465"))
    # 465 = SSL implicite ; 587 = STARTTLS. Les deux sont exclusifs.
    EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", EMAIL_PORT == 465)
    EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", EMAIL_PORT == 587) and not EMAIL_USE_SSL
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "30"))
else:
    EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "La Concorde asbl <infos@la-concorde.be>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# -----------------------------------------------------------------------
# Newsletter (application 'newsletter')
# -----------------------------------------------------------------------
# Expéditeur et adresse de réponse des newsletters (par défaut : DEFAULT_FROM_EMAIL)
NEWSLETTER_FROM_EMAIL = os.environ.get("NEWSLETTER_FROM_EMAIL", "") or DEFAULT_FROM_EMAIL
NEWSLETTER_REPLY_TO = os.environ.get("NEWSLETTER_REPLY_TO", "")
# Adresse du site utilisée dans les e-mails (liens, images) ; à défaut WAGTAILADMIN_BASE_URL
NEWSLETTER_BASE_URL = os.environ.get("NEWSLETTER_BASE_URL", "")
# Cadence d'envoi, prudente pour le serveur SMTP mutualisé d'o2switch
NEWSLETTER_LOT_TAILLE = int(os.environ.get("NEWSLETTER_LOT_TAILLE", "15"))
NEWSLETTER_PAUSE_SECONDES = float(os.environ.get("NEWSLETTER_PAUSE_SECONDES", "2"))
NEWSLETTER_MAX_PAR_HEURE = int(os.environ.get("NEWSLETTER_MAX_PAR_HEURE", "150"))
NEWSLETTER_TENTATIVES_MAX = 3
