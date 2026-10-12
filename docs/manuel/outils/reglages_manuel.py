"""
Réglages Django utilisés uniquement pour produire les captures du manuel.

Ils reprennent les réglages de développement, mais travaillent sur une
COPIE de la base et un dossier média séparé (docs/manuel/.travail/) : la
base de développement n'est jamais modifiée.
"""
from pathlib import Path

from concorde_site.settings.dev import *  # noqa

TRAVAIL = Path(__file__).resolve().parent.parent / ".travail"

DATABASES["default"]["NAME"] = TRAVAIL / "db.sqlite3"  # noqa: F405
MEDIA_ROOT = TRAVAIL / "media"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: False}
WAGTAIL_ENABLE_UPDATE_CHECK = False  # pas de bandeau « mise à jour disponible » sur les captures
