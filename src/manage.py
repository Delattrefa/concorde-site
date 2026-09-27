#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "concorde_site.settings.dev")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Impossible d'importer Django. Avez-vous activé votre environnement "
            "virtuel et installé les dépendances (pip install -r requirements.txt) ?"
        ) from exc

    execute_from_command_line(sys.argv)
