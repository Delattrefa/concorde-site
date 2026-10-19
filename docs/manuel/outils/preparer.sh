#!/usr/bin/env bash
# Prépare le site de démonstration utilisé pour les captures du manuel :
#   1. copie la base de développement (src/db.sqlite3) dans docs/manuel/.travail/
#   2. relie les dossiers de src/media/ (lecture seule en pratique)
#   3. applique les migrations et ajoute les données fictives (donnees_demo.py)
#   4. lance le serveur sur http://127.0.0.1:8765 (Ctrl+C pour l'arrêter)
#
# La base de développement n'est jamais modifiée. Relancer ce script repart
# d'une copie neuve.
set -euo pipefail

OUTILS="$(cd "$(dirname "$0")" && pwd)"
MANUEL="$(dirname "$OUTILS")"
RACINE="$(cd "$MANUEL/../.." && pwd)"
TRAVAIL="$MANUEL/.travail"
PYTHON="${PYTHON:-$RACINE/.env/bin/python}"

rm -rf "$TRAVAIL"
mkdir -p "$TRAVAIL/media"
cp "$RACINE/src/db.sqlite3" "$TRAVAIL/db.sqlite3"
for dossier in "$RACINE"/src/media/*; do
    # Les contrats générés pendant les captures restent dans .travail/.
    [ "$(basename "$dossier")" = "contrats_location" ] && continue
    ln -s "$dossier" "$TRAVAIL/media/"
done

cd "$RACINE/src"
export PYTHONPATH="$OUTILS" DJANGO_SETTINGS_MODULE=reglages_manuel
# La base de développement peut avoir du retard sur le code
"$PYTHON" manage.py migrate --noinput > /dev/null
"$PYTHON" manage.py shell < "$OUTILS/donnees_demo.py"
exec "$PYTHON" manage.py runserver 127.0.0.1:8765 --noreload
