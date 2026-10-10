# Newsletter — installation, test et envoi sur o2switch

Application `src/newsletter/` : inscription publique, gestion des abonnés et
rédaction dans l'admin Wagtail, envoi par lots via le SMTP d'o2switch.

## Fonctionnement en bref

| Élément | Où |
|---|---|
| Page d'inscription | Page Wagtail « Page d'inscription à la newsletter » (une seule) |
| Abonnés | Admin Wagtail → **Newsletter → Abonnés** (filtres, recherche, export CSV/Excel) |
| Rédaction | Admin Wagtail → **Newsletter → Newsletters** (aperçu en direct de l'e-mail) |
| Envoi | Bouton « Préparer l'envoi » dans la newsletter → test → confirmation → suivi |
| Expédition | Tâche cron toutes les 5 min : `manage.py envoyer_newsletters` |
| Désinscription | Lien personnel dans chaque e-mail + désinscription « en un clic » Gmail/Apple |

Pourquoi une tâche cron et pas Celery : l'hébergement mutualisé o2switch ne
permet ni Celery ni Redis, et son SMTP est prévu pour des envois courants.
L'envoi est donc mis en file d'attente en base de données, puis expédié par
petits lots (15 messages toutes les 5 minutes, 150 par heure au maximum par
défaut). Il reprend automatiquement après une erreur.

---

## 1. Installation en local

1. Copier les fichiers dans le projet (l'archive respecte l'arborescence).
2. Vérifier les dépendances (python-dotenv est déjà dans `requirements.txt`) :
   ```bash
   pip install -r requirements.txt
   ```
3. Créer la migration de l'application puis l'appliquer :
   ```bash
   cd src
   python manage.py makemigrations newsletter
   python manage.py migrate
   ```
   Le fichier `newsletter/migrations/0001_initial.py` ainsi créé doit être
   ajouté au dépôt Git (`git add src/newsletter`).

En local, tant que `EMAIL_HOST` n'est pas défini, **les e-mails ne partent
pas** : ils s'affichent dans le terminal de `runserver`. Aucun risque d'écrire
à de vrais abonnés pendant les essais.

## 2. Test complet en local

1. **Page d'inscription** : admin Wagtail → Pages → Accueil → *Ajouter une
   sous-page* → « Page d'inscription à la newsletter ». Titre « Newsletter »,
   publier. Ajouter le lien au menu (Paramètres → Menu principal).
2. **S'inscrire** sur `http://127.0.0.1:8000/newsletter/` avec une adresse de
   test. Vérifier le message de confirmation, puis l'abonné dans
   *Newsletter → Abonnés*.
3. **Rédiger** : *Newsletter → Newsletters → Ajouter*. Remplir l'objet,
   ajouter des blocs (titre, texte, image, bouton, actualités récentes…).
   Le bouton **Aperçu** montre l'e-mail tel qu'il sera reçu ; la barre de
   l'aperçu permet de basculer en largeur mobile.
4. **Enregistrer**, puis **« Préparer l'envoi de cette newsletter »** :
   - « Envoyer le test » : l'e-mail apparaît dans le terminal ;
   - cocher la confirmation, « Lancer l'envoi ».
5. **Expédier** la file (en production, c'est la tâche cron qui le fait) :
   ```bash
   python manage.py envoyer_newsletters --pause 0
   ```
   La page de suivi affiche alors 100 %.
6. **Désinscription** : copier le lien « Se désinscrire » affiché dans le
   terminal, l'ouvrir, confirmer. L'abonné passe à « Désinscrit ».

## 3. Mise en place sur o2switch

> Prérequis : **un nom de domaine** relié à l'hébergement. Une adresse
> d'expédition `@…odns.fr` n'est pas possible et les messages finiraient en
> spam. Tant que le domaine n'est pas prêt, laissez `EMAIL_HOST` vide.

1. **Boîte d'envoi** : cPanel → *Comptes de messagerie* → créer par exemple
   `infos@la-concorde.be` avec un mot de passe fort.
2. **Délivrabilité** : cPanel → *Délivrabilité des e-mails* : SPF et DKIM
   doivent être « Valides » (cliquer *Réparer* sinon). Ajouter aussi un
   enregistrement DMARC dans *Zone Editor* :
   `_dmarc  TXT  v=DMARC1; p=none; rua=mailto:infos@la-concorde.be`
3. **Réglages** : compléter `~/concorde/src/.env` (modèle : `src/.env.example`) :
   ```
   EMAIL_HOST=mail.la-concorde.be
   EMAIL_PORT=465
   EMAIL_HOST_USER=infos@la-concorde.be
   EMAIL_HOST_PASSWORD=le-mot-de-passe-de-la-boite
   DEFAULT_FROM_EMAIL=La Concorde asbl <infos@la-concorde.be>
   NEWSLETTER_FROM_EMAIL=La Concorde asbl <infos@la-concorde.be>
   NEWSLETTER_REPLY_TO=infos@la-concorde.be
   NEWSLETTER_BASE_URL=https://www.la-concorde.be
   ```
   Si le port 465 est refusé : `EMAIL_PORT=587` (STARTTLS, choisi automatiquement).
   Le nom du serveur figure aussi dans cPanel → *Connecter des appareils*.
4. **Déployer** : `git push` en local, puis sur le serveur
   `bash ~/concorde/deploy.sh` (applique la migration, met à jour les fichiers statiques).
5. **Tester le SMTP** :
   ```bash
   source ~/virtualenv/concorde/src/3.11/bin/activate
   cd ~/concorde/src
   export DJANGO_SETTINGS_MODULE=concorde_site.settings.production
   python manage.py sendtestemail votre.adresse@gmail.com
   ```
6. **Tâche cron** : cPanel → *Tâches Cron* → toutes les 5 minutes (`*/5 * * * *`) :
   ```
   cd ~/concorde/src && DJANGO_SETTINGS_MODULE=concorde_site.settings.production ~/virtualenv/concorde/src/3.11/bin/python manage.py envoyer_newsletters --silencieux >> ~/concorde/src/newsletter-cron.log 2>&1
   ```
   (adapter `3.11` à la version de l'application Python). Sans envoi en cours,
   la commande ne fait rien. `--silencieux` n'écrit dans le journal que les erreurs.
7. **Premier envoi réel** : faire un « Envoyer le test » vers une adresse Gmail
   et une adresse Outlook/Hotmail, vérifier l'affichage sur ordinateur et
   téléphone, et le score sur https://www.mail-tester.com (viser 9/10 ou plus).

## 4. Cadence d'envoi

Réglable dans `.env` :

| Variable | Défaut | Rôle |
|---|---|---|
| `NEWSLETTER_LOT_TAILLE` | 15 | messages par passage de la tâche cron |
| `NEWSLETTER_PAUSE_SECONDES` | 2 | pause entre deux messages |
| `NEWSLETTER_MAX_PAR_HEURE` | 150 | plafond sur une heure glissante |

o2switch ne publie pas de quota précis pour les envois groupés. Ces valeurs
sont volontairement prudentes ; demandez au support o2switch la limite
applicable avant de les augmenter. À 150 messages par heure, 600 abonnés
reçoivent la lettre en 4 heures environ. Un refus temporaire du serveur
interrompt simplement le lot, qui reprend au passage suivant.

## 5. Bonnes pratiques et RGPD

- La **case de consentement** est obligatoire sur le formulaire. N'ajoutez à
  la main (admin) que des personnes ayant donné leur accord.
- L'option **« Demander une confirmation par e-mail (double opt-in) »** de la
  page d'inscription est recommandée : elle empêche d'inscrire l'adresse d'un
  tiers et prouve le consentement.
- La politique de confidentialité a été complétée (paragraphe *Newsletter*,
  `consentement/politique.py`). Si la page existe déjà sur le site, copiez ce
  paragraphe dans la page via l'admin.
- Les désinscrits restent dans la liste (statut « Désinscrit ») pour ne plus
  leur écrire ; supprimez-les après 3 ans, comme annoncé dans la politique.
- Droit d'envoi : réservé aux superutilisateurs et aux groupes ayant la
  permission « Peut envoyer une newsletter aux abonnés » (Paramètres → Groupes).

## 6. Dépannage

| Symptôme | Piste |
|---|---|
| « Lancer l'envoi » fonctionne mais rien ne part | Tâche cron absente : voir `newsletter-cron.log`, ou bouton « Envoyer un lot maintenant » sur la page de suivi |
| Erreur d'authentification SMTP | Mot de passe ou identifiant (adresse complète) dans `.env`, puis redémarrer l'application |
| Messages en spam | SPF/DKIM/DMARC, expéditeur du même domaine que le site, score mail-tester |
| Images absentes dans l'e-mail | `NEWSLETTER_BASE_URL` doit être l'adresse publique en `https://` |
| La page de suivi signale une erreur | Lire le message affiché ; l'envoi reprend seul au passage suivant |
