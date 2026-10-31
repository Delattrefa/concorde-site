#!/bin/bash
# Mise à jour du site La Concorde sur o2switch.
# Usage (en SSH) : bash ~/concorde/deploy.sh
set -euo pipefail

PROJET="$HOME/concorde"
APP="$PROJET/src"
# Chemin affiché par cPanel > Setup Python App ("Enter to the virtual environment")
# Adapter la version de Python si besoin (ex : 3.12).
VENV="$HOME/virtualenv/concorde/src/3.11/bin/activate"

export DJANGO_SETTINGS_MODULE=concorde_site.settings.production

echo "→ Récupération du code depuis GitHub"
cd "$PROJET"
git pull --ff-only origin main

echo "→ Dépendances"
source "$VENV"
pip install --quiet -r requirements.txt

echo "→ Base de données"
cd "$APP"
python manage.py migrate --noinput

echo "→ Protection des contrats et des signatures (dossier interdit depuis Internet)"
MEDIA_ROOT=$(python -c "from django.conf import settings; import django; django.setup(); print(settings.MEDIA_ROOT)")
mkdir -p "$MEDIA_ROOT/contrats_location"
cp "$PROJET/deploiement/htaccess-contrats" "$MEDIA_ROOT/contrats_location/.htaccess"

echo "→ Médiathèque : collections Calendrier › Signature et protection des signatures"
python manage.py preparer_collections

echo "→ Fichiers statiques"
python manage.py collectstatic --noinput

echo "→ Slugs des pages sans accents (URL accentuées non servies par o2switch)"
python manage.py convertir_slugs_ascii

echo "→ Page Info : liens vers les pages libres transformés en onglets (une seule fois)"
python manage.py convertir_info_en_onglets

echo "→ Index de la recherche du site"
python manage.py update_index > /dev/null

echo "→ Adresse du site dans Wagtail (liens de partage, aperçus Facebook)"
python manage.py verifier_adresse_site

echo "→ Redémarrage de l'application"
mkdir -p "$APP/tmp"
touch "$APP/tmp/restart.txt"

echo "✓ Déploiement terminé."
