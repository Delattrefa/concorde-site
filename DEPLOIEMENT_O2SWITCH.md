# Déploiement du site La Concorde sur o2switch via GitHub

Dans ce guide, « compte » désigne l'identifiant cPanel o2switch, et
`la-concorde.be` le domaine. Remplacez-les partout par les vôtres.

Organisation retenue sur le serveur :

```
/home/compte/
├── concorde/                 ← clone du dépôt GitHub (hors du web public)
│   ├── deploy.sh
│   ├── requirements.txt      ← versions exactes installées (générées depuis requirements.in)
│   ├── requirements.in       ← dépendances directes et plages de versions
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

**Option A bis — MySQL / MariaDB.**
cPanel → **Bases de données MySQL** : créez une base, un utilisateur avec
un mot de passe solide, puis *Ajouter l'utilisateur à la base* avec
**tous les privilèges**. Notez les noms préfixés (`compte_concorde`).
Dans phpMyAdmin, onglet *Opérations* de la base, vérifiez que
l'interclassement est **utf8mb4_general_ci** (ou `utf8mb4_unicode_ci`) ;
sinon choisissez-le et validez, *avant* le premier `migrate`.

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

Pour MySQL : `DB_ENGINE=mysql`, `DB_PORT=3306`, et `DB_NAME`, `DB_USER`,
`DB_PASSWORD` créés à l'étape 5 (`DB_HOST=localhost`).

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

### Option A — contenu vers MySQL / MariaDB (ou PostgreSQL)

Procédure testée de bout en bout vers MariaDB 10.11 (version
d'o2switch) : tout le contenu est repris à l'identique.

**1. Sur votre ordinateur : préparer la base locale**

Travaillez sur une copie de sécurité, puis préparez la base :

```bash
cd src
cp db.sqlite3 db-avant-export.sqlite3
python manage.py preparer_export_mysql
```

Cette commande corrige ce que MySQL refuserait : elle fusionne les
mots-clés qui ne diffèrent que par les majuscules ou les accents
(« Theatre » / « théâtre »), retire les redirections automatiques depuis
d'anciennes adresses accentuées et l'historique des pages supprimées. Elle
s'arrête en listant tout autre doublon à corriger (rien n'est alors
modifié). Ajoutez `--dry-run` pour voir ce qu'elle ferait.

**2. Exporter le contenu**

```bash
python manage.py dumpdata --natural-foreign \
  -e contenttypes -e auth.permission -e sessions -e admin.logentry \
  -e wagtailcore.groupcollectionpermission -e wagtailcore.grouppagepermission \
  -e wagtailimages.rendition -e wagtailsearch -e wagtailcore.referenceindex \
  -e wagtailadmin.editingsession -e axes -e theatre.accesapplication \
  --indent 2 -o data.json
scp data.json compte@la-concorde.be:~/concorde/src/
```

Pas de `--natural-primary` : il fait échouer l'import des collections
d'images. Les éléments exclus sont recréés sur le serveur (miniatures,
index de recherche, droits des groupes) ou sans intérêt (sessions,
tentatives de connexion).

**3. Sur le serveur : base vide, puis import**

`src/.env` doit contenir les réglages MySQL (étape 7). Puis :

```bash
source ~/virtualenv/concorde/src/3.11/bin/activate   # même chemin que dans deploy.sh
cd ~/concorde/src
export DJANGO_SETTINGS_MODULE=concorde_site.settings.production
python manage.py migrate
python manage.py shell -c "from wagtail.models import Site, Page; Site.objects.all().delete(); Page.objects.filter(depth__gt=1).delete()"
python manage.py loaddata data.json
```

La deuxième commande supprime le site et la page « Welcome » créés par
Wagtail lors du `migrate` : sans elle, `loaddata` échoue (deux sites
« localhost » par défaut). `loaddata` annonce à la fin le nombre d'objets
installés.

**4. Remettre en place ce qui n'est pas exporté**

```bash
python manage.py preparer_collections
python manage.py update_index
python manage.py rebuild_references_index
python manage.py generer_miniatures
rm data.json
```

`generer_miniatures` recrée les miniatures de tous les albums (plusieurs
minutes) : sans elle, la première ouverture de chaque album serait très
lente. Enfin, relancez `bash ~/concorde/deploy.sh`, puis réglez l'adresse
du site dans Wagtail (ci-dessous).

**En cas d'échec de `loaddata`** : rien n'est à moitié importé (tout ou
rien). Videz la base (phpMyAdmin → la base → *Structure* → tout cocher →
*Supprimer*), corrigez la cause, puis reprenez à l'étape 3. Un message
« Duplicate entry » signale un doublon pour MySQL : relancez
`preparer_export_mysql` sur la base locale, puis réexportez.

**Si la base de production n'est pas vide**

L'import **remplace** tout le contenu de la base de production : il ne
fusionne rien. Commencez par regarder ce qu'elle contient (sur le serveur,
environnement activé comme à l'étape 3) :

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
from wagtail.models import Page
from calendrier.models import Reservation
from newsletter.models import Abonne
from theatre.models import Reservation as Billet
from wagtail.contrib.forms.models import FormSubmission
print('Pages :', Page.objects.count(), '| comptes :', get_user_model().objects.count())
print('Demandes de location :', Reservation.objects.count())
print('Abonnés newsletter :', Abonne.objects.count())
print('Réservations théâtre :', Billet.objects.count())
print('Messages de contact :', FormSubmission.objects.count(), '| dernier :', FormSubmission.objects.order_by('-submit_time').values_list('submit_time', flat=True).first())
"
```

*Cas 1 — rien à garder* (page « Welcome » de Wagtail, essais, contenu plus
ancien que la base locale) :

1. Sauvegardez quand même la base :
   ```bash
   mysqldump -u compte_concorde -p compte_concorde > ~/sauvegarde-avant-import-$(date +%F).sql
   ```
   (restauration : `mysql -u compte_concorde -p compte_concorde < ~/sauvegarde-avant-import-AAAA-MM-JJ.sql`).
2. Videz la base : phpMyAdmin → la base → *Structure* → *Tout cocher* →
   *Supprimer*, en **décochant** « Activer la vérification des clés
   étrangères ». La base et son utilisateur restent, sans aucune table.
   N'utilisez pas `python manage.py flush` à la place (il garde les
   tables ; cas non testé avec l'import).
3. Reprenez à l'étape 3 ci-dessus (`migrate`, suppression du site
   « Welcome », `loaddata`), puis l'étape 4. Choisissez un moment calme :
   le site est en erreur pendant quelques minutes.

*Cas 2 — le site en ligne a reçu des données à garder* (demandes de
location, abonnés, réservations, messages de contact, comptes, actualités
publiées en ligne) : **n'importez pas** la base locale, elle effacerait
ces données. Les deux bases ne peuvent pas être fusionnées
automatiquement (leurs éléments portent les mêmes numéros internes). Soit
la production devient la référence et le contenu présent seulement en
local est ressaisi dans l'admin (recommandé), soit on importe seulement
certains contenus (par exemple actualités et albums) avec une commande sur
mesure à développer.

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

Indispensable : Wagtail s'en sert pour toutes les adresses complètes. Avec
`localhost`, les boutons de partage envoient `http://localhost/...` et
Facebook ou WhatsApp n'affichent ni la publication ni son image.
`deploy.sh` avertit (« ⚠ Adresse du site à corriger ») tant que ce n'est
pas fait. Pour une actualité déjà partagée, faites relire la page par
Facebook : https://developers.facebook.com/tools/debug/ → *Récupérer à
nouveau*.

---

## Étape 10 — Vérifications

- `https://www.la-concorde.be/` : page d'accueil avec son style.
- `/admin/` : connexion, ajout d'une image.
- Page Médias : les albums et les miniatures s'affichent.
- Un administrateur peut télécharger un contrat depuis une réservation
  validée, mais l'adresse directe
  `https://www.la-concorde.be/media/contrats_location/...` doit renvoyer
  une erreur 403.

### Tâche cron : envoi des newsletters

Le bouton « Envoyer » de l'admin ne fait que mettre la newsletter en file
d'attente. Les e-mails partent ensuite **par petits lots**, pour respecter
les limites d'envoi du serveur. C'est une tâche cron qui expédie ces lots :
**sans elle, la newsletter reste « Envoi en cours »**, à moins de cliquer
sans arrêt sur « Envoyer un lot maintenant » dans la page de suivi.

Dans cPanel → *Tâches Cron*, choisissez « Toutes les 5 minutes »
(`*/5 * * * *`) avec la commande :

```
cd ~/concorde/src && DJANGO_SETTINGS_MODULE=concorde_site.settings.production ~/virtualenv/concorde/src/3.11/bin/python manage.py envoyer_newsletters >> ~/concorde/src/newsletter-cron.log 2>&1
```

Quand aucune newsletter n'attend, la commande s'arrête aussitôt sans rien
faire. Si un lot est déjà en cours (lancé par le cron précédent ou par
l'admin), elle ne fait rien non plus : deux lots ne tournent jamais en même
temps. Le compte rendu de chaque passage est ajouté à
`~/concorde/src/newsletter-cron.log`.

Pour vérifier, après un envoi réel : la page de suivi de la newsletter
doit avancer toute seule toutes les 5 minutes, et `newsletter-cron.log` se
remplir. L'e-mail de test (« [TEST] ») ne prouve rien : il part
immédiatement, sans passer par le cron.

---

## Mises à jour courantes

1. Sur votre ordinateur : modifier, tester, puis `git push`.
2. Sur le serveur : `bash ~/concorde/deploy.sh`

Le déploiement automatique par GitHub Actions est déconseillé ici :
o2switch n'accepte le SSH que depuis des IP autorisées, et celles de
GitHub changent en permanence.

---

## Galerie : envoi par lots et miniatures (octobre 2026)

Cette mise à jour envoie les photos par lots avec une barre de progression,
et génère les miniatures des photos dès leur envoi. Les albums déjà en
ligne n'ont pas encore toutes leurs miniatures : sans l'étape 2, la
première ouverture de chacun d'eux reste très lente.

1. **Sur le serveur** : `bash ~/concorde/deploy.sh` (publie aussi le
   nouveau CSS de la galerie via `collectstatic`).
2. **Une seule fois**, générer les miniatures des albums existants :
   ```bash
   source ~/virtualenv/concorde/src/3.11/bin/activate   # même chemin que dans deploy.sh
   cd ~/concorde/src
   export DJANGO_SETTINGS_MODULE=concorde_site.settings.production
   python manage.py generer_miniatures
   ```
   La commande affiche le nombre d'images traitées par album. Elle peut
   être relancée sans risque (les miniatures existantes sont conservées),
   ou limitée à un album : `--album <identifiant>`.
3. **Vérifications** : ouvrir un album déjà en ligne (affichage immédiat),
   puis ajouter quelques photos depuis le site et suivre la barre de
   progression.

---

## Passage de Wagtail 6.4 à 7.4 (LTS)

Wagtail 6.4 ne reçoit plus de correctifs de sécurité depuis août 2025 ;
7.4 est maintenue jusqu'au 2 novembre 2027. Le passage ajoute des
migrations Wagtail (non annulables sans sauvegarde) : **sauvegarder la
base juste avant**.

1. **Python** : cPanel → *Setup Python App* doit indiquer Python 3.10 ou
   plus (3.11 conseillé, comme dans `deploy.sh`).
2. **Sauvegarde de la base** (en SSH), selon `DB_ENGINE` dans `src/.env` :
   ```bash
   # SQLite
   cp ~/concorde/src/db.sqlite3 ~/sauvegarde-avant-wagtail7.sqlite3
   # PostgreSQL
   pg_dump -U compte_concorde -h localhost compte_concorde > ~/sauvegarde-avant-wagtail7.sql
   # MySQL / MariaDB
   mysqldump -u compte_concorde -p compte_concorde > ~/sauvegarde-avant-wagtail7.sql
   ```
   Noter aussi le commit en ligne : `git -C ~/concorde rev-parse HEAD`.
3. **Sur votre ordinateur** : intégrer la branche puis publier :
   `git checkout main && git merge wagtail-7.4 && git push`.
4. **Sur le serveur** : `bash ~/concorde/deploy.sh` (installe les nouvelles
   versions, applique les migrations et reconstruit l'index de recherche).
5. **Vérifications** : pages du site et recherche ; dans l'admin, ouvrir,
   modifier et publier une page ; listes des snippets ; envoi de test d'une
   newsletter.

**Retour arrière** si besoin : restaurer la sauvegarde de la base
(recopier le fichier SQLite, ou `psql … < sauvegarde.sql` /
`mysql … < sauvegarde.sql` dans une base vidée), puis
`git -C ~/concorde checkout <commit noté>`, réinstaller les dépendances
(`pip install -r ~/concorde/requirements.txt` dans l'environnement
virtuel) et redémarrer (`touch ~/concorde/src/tmp/restart.txt`).

---

## Sécurité des connexions (octobre 2026)

Cette mise à jour bloque pendant 15 minutes une adresse IP après 5 mots
de passe erronés (sur `/connexion/`, `/admin/` et `/django-admin/`),
impose des mots de passe d'au moins 10 caractères (pour les nouveaux
mots de passe seulement) et passe la protection HSTS à un an.

1. **Sur le serveur** : `bash ~/concorde/deploy.sh` (installe
   `django-axes` et crée ses tables).
2. **Dans `src/.env`**, remplacer `SECURE_HSTS_SECONDS=3600` par
   `SECURE_HSTS_SECONDS=31536000` (ou supprimer la ligne), puis
   `touch ~/concorde/src/tmp/restart.txt`.
3. **Vérifier** : `curl -sI https://www.la-concorde.be/ | grep -i strict`
   doit afficher `max-age=31536000`.

Les tentatives échouées sont consultables dans l'administration Django
(*Axes → Access attempts*).

---

## Médiathèque : signatures des contrats (octobre 2026)

À chaque déploiement, `deploy.sh` lance `python manage.py preparer_collections`,
qui ne fait rien si tout est déjà en ordre :

- crée les collections **Calendrier** et **Calendrier › Signature** si elles
  manquent (une collection « Signature » rangée ailleurs est déplacée, avec
  ses images) ;
- réserve **Signature** aux super-utilisateurs dans l'admin Wagtail. Wagtail
  fait hériter les droits d'une collection à ses sous-collections : les
  droits des groupes (Editors, Moderators…) sur les images de *Root* ou de
  *Calendrier* sont donc reportés sur les autres collections. Conséquence :
  les images rangées directement dans *Root* ou dans *Calendrier* ne sont
  plus visibles que des super-utilisateurs ;
- range le fichier de chaque signature dans `media/contrats_location/signatures/`
  sous un nom aléatoire (dossier interdit depuis Internet par le même
  `.htaccess` que les contrats). Une image ajoutée plus tard dans la
  collection Signature est rangée aussitôt.

Une **nouvelle collection** créée plus tard à la racine n'est accessible
qu'aux super-utilisateurs : donner les droits aux groupes dans
*Paramètres → Groupes → Editors → Permissions sur les collections d'images*.

**Vérification indispensable** (une fois) : le dossier des contrats doit
être interdit depuis Internet (réponse 403) :

```bash
MEDIA_ROOT=$(grep ^MEDIA_ROOT= ~/concorde/src/.env | cut -d= -f2)
echo test > "$MEDIA_ROOT/contrats_location/test.txt"
curl -s -o /dev/null -w "%{http_code}\n" https://www.la-concorde.be/media/contrats_location/test.txt
rm "$MEDIA_ROOT/contrats_location/test.txt"
```

Si le résultat est 200, les contrats et les signatures sont lisibles par
n'importe qui : prévenir le responsable technique.

---

## Agenda Google Workspace partagé (octobre 2026)

Les activités du calendrier (publiques et privées) et les locations
**validées** sont recopiées automatiquement dans un agenda Google partagé.
Le sens est unique : le site reste la référence, et une modification faite
dans Google est écrasée à la synchronisation suivante. Une location refusée,
annulée (statut ou contrat annulé) ou supprimée est retirée de l'agenda.
Seul le nom du client y figure : ses coordonnées restent sur le site.
Les événements ajoutés à la main dans l'agenda ne sont jamais touchés.

**1. L'agenda.** Dans Google Agenda (compte Workspace) : *Autres agendas* →
**+** → *Créer un agenda* (ex. « La Concorde — Calendrier »), puis
partagez-le avec l'équipe.

**2. Le compte de service** (le « robot » qui écrit dans l'agenda), sur
https://console.cloud.google.com :

1. Créez un projet (ex. « site-la-concorde »).
2. *API et services* → *Bibliothèque* → **Google Calendar API** → *Activer*.
3. *IAM et administration* → *Comptes de service* → *Créer un compte de
   service* (ex. « agenda-site »), sans rôle. Notez son adresse,
   `agenda-site@site-la-concorde.iam.gserviceaccount.com`.
4. Ouvrez-le → *Clés* → *Ajouter une clé* → *Créer une clé* → **JSON**. Le
   fichier téléchargé est un **secret** : il donne accès à l'agenda.

**3. Autoriser le partage externe** (le robot est extérieur au domaine) :
console d'administration Workspace → *Applications* → *Google Workspace* →
*Agenda* → *Paramètres de partage* → *Options de partage externe* :
« Partager toutes les informations, et autoriser les personnes externes à
modifier les agendas ».

**4. Partager l'agenda avec le robot** : paramètres de l'agenda → *Partager
avec des personnes* → l'adresse du robot, droit **« Apporter des
modifications aux événements »**. Dans la même page, rubrique *Intégrer
l'agenda*, copiez l'**ID de l'agenda** (`…@group.calendar.google.com`).

**4 bis. Si Google refuse le partage avec le robot** (fréquent avec
Workspace) : utilisez la **délégation au niveau du domaine**. Le robot agit
alors au nom d'un utilisateur du domaine qui a déjà accès à l'agenda, sans
partage :

1. Google Cloud → *IAM et administration* → *Comptes de service* → le
   robot → copiez son **ID client** (un long nombre, « OAuth 2 Client ID »).
2. Console d'administration Workspace → *Sécurité* → *Accès et contrôle
   des données* → *Commandes des API* → *Gérer la délégation au niveau du
   domaine* → *Ajouter* : l'ID client, et le champ d'application
   `https://www.googleapis.com/auth/calendar.events`. Autorisez.
3. Vérifiez que l'utilisateur choisi (ex. `infos@la-concorde.be`) peut
   **modifier les événements** de l'agenda (il en est propriétaire, ou il
   y a le droit « Apporter des modifications aux événements »).
4. Ajoutez au `.env` (étape 6) :
   `GOOGLE_AGENDA_UTILISATEUR=infos@la-concorde.be`.

La délégation peut mettre quelques minutes (parfois jusqu'à une heure) à
s'appliquer. « unauthorized_client » signale qu'elle n'est pas encore
active, ou que l'ID client ou le champ d'application est incorrect.

**5. La clé sur le serveur**, hors du dossier public :

```bash
scp cle-telechargee.json compte@la-concorde.be:~/concorde/google-agenda.json
ssh compte@la-concorde.be chmod 600 ~/concorde/google-agenda.json
```

Supprimez ensuite la clé de votre ordinateur. Elle ne doit pas aller sur
GitHub : `google-agenda*.json` est ignoré par git.

**6. Le `.env`**, puis le redémarrage :

```ini
GOOGLE_AGENDA_ID=abc123…@group.calendar.google.com
GOOGLE_AGENDA_CLE=/home/compte/concorde/google-agenda.json
# seulement avec la délégation (4 bis) :
GOOGLE_AGENDA_UTILISATEUR=infos@la-concorde.be
```

```bash
touch ~/concorde/src/tmp/restart.txt
```

**7. Première recopie :**

```bash
source ~/virtualenv/concorde/src/3.11/bin/activate
cd ~/concorde/src
export DJANGO_SETTINGS_MODULE=concorde_site.settings.production
python manage.py synchroniser_agenda_google
```

Sans la ligne `export`, Django prend les réglages de développement et
s'arrête sur « no such table: calendrier_activite » (il ouvre une base
SQLite vide au lieu de celle du site).

Pour ne recopier que le présent et l'avenir, ajoutez par exemple
`--depuis 2026-01-01`.

**8. Tâche cron de nuit**, qui rattrape les échecs : si Google est
injoignable au moment d'un enregistrement, le site fonctionne normalement
et l'erreur va dans `django-erreurs.log`. Dans cPanel → *Tâches Cron*,
ajoutez par exemple chaque jour à 3 h 15 :

```bash
cd ~/concorde/src && DJANGO_SETTINGS_MODULE=concorde_site.settings.production ~/virtualenv/concorde/src/3.11/bin/python manage.py synchroniser_agenda_google --depuis $(date -d '-1 year' +\%F) > /dev/null
```

(`\%` : cron interprète `%` comme un retour à la ligne.)

Pour arrêter la recopie, videz `GOOGLE_AGENDA_ID` dans le `.env` et
redémarrez. Les événements déjà créés restent dans l'agenda.

---

## Statistiques de fréquentation (octobre 2026)

Le site compte lui-même ses visites (application `statistiques`) : sans
cookie, sans service extérieur, sans enregistrer d'adresse IP. Les chiffres
se consultent dans Wagtail, menu **Statistiques** (`/admin/statistiques/`).
Ce menu est visible des super-utilisateurs et des comptes ayant la
permission « Peut consulter les statistiques de fréquentation ».

Mise en service : `bash ~/concorde/deploy.sh` (crée les tables). Les
chiffres commencent le jour du déploiement : il n'y a pas d'historique.

**Rien d'autre à installer.** Pas de tâche cron : le premier visiteur de
chaque jour efface les empreintes de la veille, et les totaux de plus de
25 mois (`STATISTIQUES_CONSERVATION_JOURS`).

**Politique de confidentialité.** Le texte d'origine disait « aucun outil
de mesure d'audience ». La commande `creer_page_confidentialite` ne modifie
jamais une page existante : il faut donc mettre à jour la page en ligne
à la main dans Wagtail.
- Dans « En résumé », remplacer la dernière phrase par : « Le site ne fait
  aucune publicité ; il compte ses visites lui-même, de façon anonyme et sans
  cookie. »
- Au point 2, sous « Navigation sur le site », ajouter le paragraphe
  « Statistiques de fréquentation » de `src/consentement/politique.py`.

---

## Dépannage

| Symptôme | Cause probable / solution |
|---|---|
| Page « Incomplete response » ou erreur 500 | Lire `~/concorde/src/passenger.log` et `django-erreurs.log`. Souvent une valeur manquante dans `.env` ou un module absent (`pip install -r requirements.txt` dans le bon environnement). |
| `KeyError: 'SECRET_KEY'` | Le fichier `src/.env` est absent ou mal placé. |
| Newsletter restée « en cours d'envoi » | La tâche cron `envoyer_newsletters` est absente ou en échec (voir « Tâche cron : envoi des newsletters », étape 10). Lire `~/concorde/src/newsletter-cron.log`. |
| Les commandes `manage.py` utilisent SQLite / DEBUG | Oubli de `export DJANGO_SETTINGS_MODULE=concorde_site.settings.production` (le script `deploy.sh` le fait). |
| Site sans mise en forme | `collectstatic` non exécuté : relancer `deploy.sh`. |
| Photos en erreur 404 | Vérifier que `MEDIA_ROOT` est bien dans le dossier public du domaine. En dernier recours : `SERVE_MEDIA=1` dans `.env`, puis redémarrer. |
| Boucle de redirection | Certificat HTTPS absent ou en cours : `SECURE_SSL_REDIRECT=0` le temps de régler le certificat. |
| « CSRF verification failed » | Domaine manquant dans `ALLOWED_HOSTS`. |
| Envoi groupé de photos refusé | Les photos partent par lots de 10 : les fichiers refusés sont listés sous la barre de progression (20 Mo maximum par photo, JPEG, PNG, WebP ou GIF). Sans JavaScript, l'envoi se fait en une fois, limité à 200 fichiers. |
| Première ouverture d'un album très lente | Miniatures pas encore générées : `python manage.py generer_miniatures` (voir « Galerie : envoi par lots et miniatures »). |
| Page en erreur 404 alors qu'elle existe | Slug accentué (o2switch ne sert pas les URL accentuées) : `python manage.py convertir_slugs_ascii` (lancé aussi par `deploy.sh`). Les nouveaux slugs sont convertis automatiquement dans l'administration. |
| Page « Connexion bloquée » | 5 mots de passe erronés depuis la même adresse IP : patienter 15 minutes, ou débloquer en SSH avec `python manage.py axes_reset_ip <adresse IP>` (`axes_reset` débloque tout le monde). |
| Un administrateur ne voit plus certaines images dans Wagtail | Images rangées directement dans *Root* ou *Calendrier* : réservées aux super-utilisateurs depuis la protection des signatures. Les déplacer dans une autre collection (ex. « images du site »). |
| Partage Facebook/WhatsApp sans aperçu, liens en `http://localhost/...` | Adresse du site non réglée dans Wagtail : *Paramètres* → *Sites* → `www.la-concorde.be`, port `443`. Puis https://developers.facebook.com/tools/debug/ → *Récupérer à nouveau* pour les actualités déjà partagées. |
| Activité ou location absente de l'agenda Google | Voir `django-erreurs.log` (lignes « Agenda Google »). « invalid_grant » : clé JSON supprimée ou mauvais fichier. « unauthorized_client » : délégation au niveau du domaine pas encore active ou mal réglée (étape 4 bis). « 403 » / « 404 » : agenda non partagé avec l'adresse du robot (droit « Apporter des modifications aux événements ») ou mauvais `GOOGLE_AGENDA_ID`. Puis `python manage.py synchroniser_agenda_google`. |
| Modifications non visibles | `touch ~/concorde/src/tmp/restart.txt`, ou bouton *Restart* dans Setup Python App. |

Sauvegardes : o2switch sauvegarde le compte chaque jour (outil *JetBackup*
dans cPanel), base de données et médias compris.
