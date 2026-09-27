# Déploiement du site La Concorde sur o2switch via GitHub

Dans ce guide, « compte » désigne l'identifiant cPanel o2switch, et
`la-concorde.be` le domaine. Remplacez-les partout par les vôtres.

Organisation retenue sur le serveur :

```
/home/compte/
├── concorde/                 ← clone du dépôt GitHub (hors du web public)
│   ├── deploy.sh
│   ├── requirements.txt
│   ├── deploiement/htaccess-contrats
│   └── src/                  ← racine de l'application Python (cPanel)
│       ├── manage.py
│       ├── passenger_wsgi.py
│       ├── .env              ← créé à la main sur le serveur, jamais sur GitHub
│       └── staticfiles/      ← généré par collectstatic
└── public_html/              ← dossier public du domaine
    └── media/                ← photos, images Wagtail, documents
```

Le code et le fichier `.env` restent hors de `public_html`. Seuls les
médias y sont placés, pour qu'Apache les serve directement.

---

## Étape 1 — Publier le projet sur GitHub (sur votre ordinateur)

1. Créez un dépôt **privé** vide sur GitHub, par exemple `concorde-site`.
2. Dans le dossier du projet (celui qui contient `src/` et `README.md`) :

```bash
git init
git add .
git status          # VÉRIFIER la liste avant de valider (voir ci-dessous)
git commit -m "Site La Concorde — version initiale"
git branch -M main
git remote add origin git@github.com:VOTRE_COMPTE/concorde-site.git
git push -u origin main
```

Avant le `commit`, `git status` ne doit lister **aucun** de ces éléments :
`src/media/`, `src/db.sqlite3`, `.env`, `__pycache__`. Le dossier
`src/media/contrats_location/` contient des contrats avec des données
personnelles : il ne doit jamais se retrouver sur GitHub.

---

## Étape 2 — Accès SSH à o2switch

1. cPanel → **Autorisation SSH** : ajoutez l'adresse IP de votre connexion
   actuelle. o2switch refuse les connexions SSH depuis une IP non listée
   (à refaire si votre IP change).
2. Testez depuis votre ordinateur :

```bash
ssh compte@la-concorde.be
```

Le mot de passe est celui de cPanel. Le **Terminal** intégré à cPanel
fonctionne aussi pour toutes les commandes ci-dessous.

---

## Étape 3 — Relier le serveur à GitHub (clé de déploiement)

Sur le serveur :

```bash
ssh-keygen -t ed25519 -C "o2switch-concorde" -f ~/.ssh/github_concorde -N ""
cat ~/.ssh/github_concorde.pub
```

Copiez la clé affichée dans GitHub : dépôt → *Settings* → *Deploy keys* →
*Add deploy key* (laisser « Allow write access » décoché).

Toujours sur le serveur :

```bash
cat >> ~/.ssh/config <<'CONF'
Host github.com
  IdentityFile ~/.ssh/github_concorde
  IdentitiesOnly yes
CONF
chmod 600 ~/.ssh/config
ssh -T git@github.com        # répondre "yes" ; message "successfully authenticated"
cd ~
git clone git@github.com:VOTRE_COMPTE/concorde-site.git concorde
```

---

## Étape 4 — Certificat HTTPS

cPanel → **Let's Encrypt SSL** (ou *SSL/TLS Status*) : générez le
certificat pour `la-concorde.be` et `www.la-concorde.be`.

Le site redirige tout vers HTTPS. Sans certificat actif, il serait
inaccessible. Si vous devez tester avant, mettez `SECURE_SSL_REDIRECT=0`
dans `.env`.

---

## Étape 5 — Base de données

Deux possibilités.

**Option A — PostgreSQL (recommandé pour la durée).**
cPanel → **Bases de données PostgreSQL** : créez une base, un utilisateur,
puis associez l'utilisateur à la base avec tous les privilèges. cPanel
préfixe les noms (`compte_concorde`) : notez-les tels quels.

**Option B — SQLite (le plus simple).**
Aucune base à créer : on réutilise le fichier `db.sqlite3` actuel, avec
tout le contenu déjà saisi. Suffisant pour un site associatif à trafic
modéré. Voir étape 9, option B.

---

## Étape 6 — Créer l'application Python dans cPanel

cPanel → **Setup Python App** → **Create Application** :

| Champ | Valeur |
|---|---|
| Python version | la plus récente proposée (3.12 conseillé, 3.10 minimum) |
| Application root | `concorde/src` |
| Application URL | `la-concorde.be` (chemin vide) |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |
| Passenger log file | `/home/compte/concorde/src/passenger.log` |

Cliquez sur **Create**. En haut de la page, cPanel affiche la commande
« Enter to the virtual environment », par exemple :

```
source /home/compte/virtualenv/concorde/src/3.12/bin/activate && cd /home/compte/concorde/src
```

Si le chemin ou la version diffère, corrigez la variable `VENV` en haut
de `deploy.sh` (puis validez la modification sur GitHub).

cPanel peut remplacer `passenger_wsgi.py` par un fichier de démonstration.
Restaurez le vôtre :

```bash
cd ~/concorde && git checkout src/passenger_wsgi.py
```

---

## Étape 7 — Fichier de configuration `.env`

```bash
cd ~/concorde/src
cp .env.example .env
nano .env
```

Remplissez chaque valeur (clé secrète, domaines, base de données,
chemins avec votre identifiant cPanel). Pour générer la clé secrète :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Pour l'option B (SQLite) : `DB_ENGINE=sqlite` et
`DB_NAME=/home/compte/concorde/src/db.sqlite3`.

Si le domaine est un domaine supplémentaire (et non le domaine principal
du compte), son dossier public n'est pas `public_html` : vérifiez-le dans
cPanel → *Domaines*, et adaptez `MEDIA_ROOT`.

Protégez le fichier : `chmod 600 .env`

---

## Étape 8 — Premier déploiement

```bash
bash ~/concorde/deploy.sh
```

Le script installe les dépendances, applique les migrations, rassemble
les fichiers statiques, protège le dossier des contrats et redémarre
l'application.

---

## Étape 9 — Transférer le contenu existant

### Les médias (photos, images, documents)

Depuis votre ordinateur, dans le dossier du projet :

```bash
rsync -avz src/media/ compte@la-concorde.be:~/public_html/media/
```

(Ou compressez `src/media` en zip, envoyez-le par le *Gestionnaire de
fichiers* de cPanel dans `public_html/`, puis « Extraire ».)

Relancez ensuite `bash ~/concorde/deploy.sh` pour remettre en place la
protection du dossier `contrats_location`.

### Option A — contenu vers PostgreSQL

Sur votre ordinateur (réglages de développement, base SQLite) :

```bash
cd src
python manage.py dumpdata --natural-foreign --natural-primary \
  -e contenttypes -e auth.permission -e sessions -e admin.logentry \
  -e wagtailcore.groupcollectionpermission -e wagtailcore.grouppagepermission \
  -e wagtailimages.rendition -e wagtailsearch.indexentry \
  -e wagtailcore.referenceindex \
  --indent 2 -o data.json
scp data.json compte@la-concorde.be:~/concorde/src/
```

Sur le serveur (la base PostgreSQL doit avoir reçu les migrations, étape 8) :

```bash
source ~/virtualenv/concorde/src/3.12/bin/activate
cd ~/concorde/src
export DJANGO_SETTINGS_MODULE=concorde_site.settings.production
python manage.py loaddata data.json
python manage.py update_index
python manage.py rebuild_references_index
rm data.json
```

Si `loaddata` signale un conflit sur la page d'accueil ou le site par
défaut créés par Wagtail lors des migrations, videz la base
(cPanel → phpPgAdmin, ou supprimez et recréez la base), relancez
`python manage.py migrate`, supprimez le site et la page de bienvenue par
défaut, puis relancez `loaddata`. En cas de blocage, l'option B reste
possible à tout moment.

### Option B — copier la base SQLite

```bash
scp src/db.sqlite3 compte@la-concorde.be:~/concorde/src/db.sqlite3
```

Puis sur le serveur : `bash ~/concorde/deploy.sh`. Les comptes
utilisateurs, pages, albums et réservations sont repris tels quels.

### Compte administrateur

Si vous n'avez pas repris la base existante :

```bash
python manage.py createsuperuser
```

### Adresse du site dans Wagtail

Admin Wagtail → *Paramètres* → *Sites* : remplacez `localhost` par
`www.la-concorde.be`, port `443`.

---

## Étape 10 — Vérifications

- `https://www.la-concorde.be/` : page d'accueil avec son style.
- `/admin/` : connexion, ajout d'une image.
- Page Médias : les albums et les miniatures s'affichent.
- Un administrateur peut télécharger un contrat depuis une réservation
  validée, mais l'adresse directe
  `https://www.la-concorde.be/media/contrats_location/...` doit renvoyer
  une erreur 403.

---

## Mises à jour courantes

1. Sur votre ordinateur : modifier, tester, puis `git push`.
2. Sur le serveur : `bash ~/concorde/deploy.sh`

Le déploiement automatique par GitHub Actions est déconseillé ici :
o2switch n'accepte le SSH que depuis des IP autorisées, et celles de
GitHub changent en permanence.

---

## Dépannage

| Symptôme | Cause probable / solution |
|---|---|
| Page « Incomplete response » ou erreur 500 | Lire `~/concorde/src/passenger.log` et `django-erreurs.log`. Souvent une valeur manquante dans `.env` ou un module absent (`pip install -r requirements.txt` dans le bon environnement). |
| `KeyError: 'SECRET_KEY'` | Le fichier `src/.env` est absent ou mal placé. |
| Les commandes `manage.py` utilisent SQLite / DEBUG | Oubli de `export DJANGO_SETTINGS_MODULE=concorde_site.settings.production` (le script `deploy.sh` le fait). |
| Site sans mise en forme | `collectstatic` non exécuté : relancer `deploy.sh`. |
| Photos en erreur 404 | Vérifier que `MEDIA_ROOT` est bien dans le dossier public du domaine. En dernier recours : `SERVE_MEDIA=1` dans `.env`, puis redémarrer. |
| Boucle de redirection | Certificat HTTPS absent ou en cours : `SECURE_SSL_REDIRECT=0` le temps de régler le certificat. |
| « CSRF verification failed » | Domaine manquant dans `ALLOWED_HOSTS`. |
| Envoi groupé de photos refusé | Envoyer moins de photos à la fois ; la limite est de 200 fichiers et 20 Mo par photo. |
| Modifications non visibles | `touch ~/concorde/src/tmp/restart.txt`, ou bouton *Restart* dans Setup Python App. |

Sauvegardes : o2switch sauvegarde le compte chaque jour (outil *JetBackup*
dans cPanel), base de données et médias compris.
