"""
Réglages de production (hébergement o2switch via cPanel « Setup Python App »).

Toutes les valeurs sensibles ou propres au serveur sont lues dans le
fichier src/.env (jamais versionné sur GitHub) ou dans les variables
d'environnement définies dans cPanel. Voir .env.example pour la liste.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

from .base import *  # noqa

# Charge src/.env : indispensable pour que les commandes lancées en SSH
# (migrate, collectstatic, createsuperuser...) voient les mêmes réglages
# que le site servi par Passenger.
load_dotenv(BASE_DIR / ".env")

DEBUG = False

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS]

# -----------------------------------------------------------------------
# Base de données : PostgreSQL (recommandé, disponible sur o2switch),
# MySQL/MariaDB, ou SQLite (le plus simple pour un petit site).
# -----------------------------------------------------------------------
DB_ENGINE = os.environ.get("DB_ENGINE", "postgresql").lower()

if DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DB_NAME", str(BASE_DIR / "db.sqlite3")),
        }
    }
elif DB_ENGINE == "mysql":
    import pymysql

    pymysql.install_as_MySQLdb()
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ["DB_NAME"],
            "USER": os.environ["DB_USER"],
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "3306"),
            "OPTIONS": {"charset": "utf8mb4",
                        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",},
        }
    }
    SILENCED_SYSTEM_CHECKS = ["models.w036"]
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["DB_NAME"],
            "USER": os.environ["DB_USER"],
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }

# -----------------------------------------------------------------------
# Fichiers statiques (servis par WhiteNoise, déjà configuré dans base.py)
# et médias (photos de la galerie, images Wagtail, documents).
#
# Sur o2switch, on place les médias dans le dossier public du domaine
# (ex : /home/<compte>/public_html/media) pour qu'Apache les serve
# directement, sans passer par Django.
# -----------------------------------------------------------------------
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles"))
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))
MEDIA_URL = "/media/"

# Solution de secours si Apache ne sert pas /media/ : SERVE_MEDIA=1 dans
# .env fait servir les médias par Django (voir concorde_site/urls.py).
SERVE_MEDIA = os.environ.get("SERVE_MEDIA", "0") == "1"

# Ajout groupé de photos dans un album (media_gallery) : Django refuse par
# défaut plus de 100 fichiers par envoi.
DATA_UPLOAD_MAX_NUMBER_FILES = 200
WAGTAILIMAGES_MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 Mo par photo

# -----------------------------------------------------------------------
# Sécurité HTTPS
# Activer le certificat Let's Encrypt AVANT la mise en ligne, sinon la
# redirection HTTPS rend le site inaccessible.
# -----------------------------------------------------------------------
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
# HSTS : commencer court (1 heure), puis passer à 31536000 une fois le
# site validé en HTTPS sur tous les sous-domaines.
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False

WAGTAILADMIN_BASE_URL = os.environ.get("BASE_URL", "https://www.la-concorde.be")

# Journalisation des erreurs dans un fichier lisible via SSH / cPanel.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "fichier": {
            "class": "logging.FileHandler",
            "filename": os.environ.get("LOG_FILE", str(BASE_DIR / "django-erreurs.log")),
            "level": "ERROR",
        },
    },
    "loggers": {
        "django": {"handlers": ["fichier"], "level": "ERROR", "propagate": True},
    },
}
