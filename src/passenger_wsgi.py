"""
Point d'entrée attendu par Phusion Passenger (outil "Setup Python App" de
cPanel/o2switch). Ce fichier doit se trouver à la racine de l'application
Python définie dans cPanel, et exposer une variable nommée 'application'.

Il se contente de déléguer à l'application WSGI standard de Django, déjà
définie dans concorde_site/wsgi.py.
"""
import os
import sys

# Ajoute la racine du projet au chemin Python (utile si l'outil cPanel
# exécute ce fichier depuis un autre répertoire de travail).
sys.path.insert(0, os.path.dirname(__file__))

# concorde_site/wsgi.py définit déjà DJANGO_SETTINGS_MODULE vers
# 'concorde_site.settings.production' par défaut : aucune variable
# d'environnement supplémentaire n'est requise pour ce point précis.
from concorde_site.wsgi import application  # noqa: E402
