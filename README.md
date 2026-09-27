# Site La Concorde asbl — Wagtail

Site vitrine pour une ASBL culturelle (théâtre / événements), construit avec
[Wagtail CMS](https://wagtail.org/) sur Django. Inspiré de la structure du
site https://www.la-concorde.be (accueil, médias, calendrier, infos,
contact), avec une page d'accueil en défilement continu et effets de fondu.

## Fonctionnalités

- **Page d'accueil** : bandeau d'ouverture avec fondu/zoom, sections illimitées
  qui apparaissent en fondu au fil du défilement (`home` app).
- **Page Actualités / Blog** : articles datés, avec image mise en avant, mots-clés
  (tags), filtrage par mot-clé, pagination. Tout utilisateur connecté peut
  publier, modifier et supprimer directement une actualité depuis le site
  (titre, résumé, contenu, image, lien hypertexte facultatif) — la
  modification/suppression côté site est réservée à l'auteur de
  l'actualité. Depuis l'admin Wagtail, un éditeur peut créer, modifier,
  supprimer et consulter n'importe quelle actualité (`news` app).
- **Calendrier des activités & réservations de salle** (`calendrier` app) :
  calendrier mensuel avec navigation par boutons et listes déroulantes ;
  ajout, modification et suppression d'activités publiques/privées par les
  membres connectés ; demande de réservation de salle par formulaire public
  (sans connexion) ; validation ou refus des demandes par un administrateur.
  Voir détails ci-dessous.
- **Page Médias** : albums photos avec galerie et lightbox. Les
  administrateurs (`is_staff`) peuvent ajouter plusieurs photos en une
  seule fois à un album (bouton "+ Ajouter des photos" sur la page de
  l'album), plutôt que de les ajouter une par une depuis l'admin Wagtail
  (`media_gallery` app).
- **Page Infos** : contenu flexible par blocs — titres, texte, images, encarts,
  liens utiles (`info` app, StreamField).
- **Page Contact** : formulaire natif Wagtail avec envoi d'e-mail, coordonnées,
  carte Google Maps intégrable (`contact` app).
- **Recherche** : moteur de recherche interne sur toutes les pages publiées,
  accessible depuis la barre du menu (`search` app).
- **Menu principal et pied de page** : entièrement gérables depuis l'admin
  (snippets `MainMenu` / `FooterMenu`), sans toucher au code (`navigation` app).

## Installation (développement)

```bash
python -m venv venv
source venv/bin/activate        # sous Windows : venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Le site est alors accessible sur http://localhost:8000 et l'admin Wagtail sur
http://localhost:8000/admin/.

## Premiers pas dans l'admin

1. **Créer la page d'accueil** : dans *Pages*, supprimez ou remplacez la page
   "Welcome to Wagtail" par défaut par une page de type **Page d'accueil**,
   puis définissez-la comme racine du site (*Paramètres > Sites*).
2. **Ajouter les pages principales** sous la page d'accueil :
   - une page **Page actualités** (elle contiendra vos **Articles d'actualité**,
     chacun avec une date, une image, des mots-clés et un contenu par blocs),
   - une page **Page médias** (elle contiendra vos **Albums photo**),
   - une page **Page d'informations**,
   - une page **Page de contact** (ajoutez les champs du formulaire :
     nom, e-mail, message…).
3. **Configurer le menu** : dans *Snippets > Menu principal*, ajoutez un
   élément par page (ou lien externe) à afficher dans le menu. Le lien
   "Réservations" vers le calendrier des activités est ajouté
   automatiquement, pas besoin de l'ajouter manuellement.
4. **Configurer le pied de page** : dans *Snippets > Liens du pied de page*.
5. **Coordonnées & réseaux sociaux** : dans *Paramètres > Coordonnées & réseaux
   sociaux* (adresse, téléphone, e-mail). Les réseaux sociaux sont une liste
   de liens : ajoutez-en autant que voulu, y compris plusieurs pour le même
   réseau (ex : une page Facebook et un groupe Facebook), chacun avec un
   libellé facultatif pour les distinguer dans le pied de page.

## Déploiement en production

La procédure complète pour o2switch (cPanel, Passenger, dépôt GitHub) est
dans [`DEPLOIEMENT_O2SWITCH.md`](DEPLOIEMENT_O2SWITCH.md).

- Réglages : `concorde_site.settings.production`, alimentés par `src/.env`
  (modèle : `src/.env.example`).
- Base de données : PostgreSQL recommandé ; MySQL et SQLite possibles
  (`DB_ENGINE`).
- Mise à jour du serveur : `bash ~/concorde/deploy.sh`.

## Structure du projet

```
concorde_site/
├── concorde_site/        # réglages Django, urls.py, wsgi.py
├── home/                  # page d'accueil (défilement + fondu)
├── news/                   # page actualités/blog (articles, tags, pagination)
├── calendrier/              # calendrier d'activités + réservations de salle
├── theatre/                  # gestion des places de théâtre (site secondaire, /theatre/)
├── page_libre/                # pages libres (logo/titres, sections, galerie miniatures)
├── media_gallery/         # page médias + albums photos
├── info/                  # page infos pratiques (StreamField)
├── contact/                # page contact (formulaire Wagtail)
├── search/                 # recherche interne
├── navigation/             # menu principal + pied de page
├── templates/               # base.html commun
└── static/
    ├── css/main.css         # design + animations de fondu
    └── js/
        ├── scroll-effects.js  # fondu au défilement (IntersectionObserver)
        └── lightbox.js         # galerie photo en lightbox
```

## Application "news" (actualités) — gestion des droits

- **Depuis le site public** : tout utilisateur connecté peut publier une
  actualité (`/ajouter-actualite/`). Il peut ensuite la **modifier**
  (`/modifier-actualite/<id>/`) ou la **supprimer**
  (`/supprimer-actualite/<id>/`) — mais uniquement les actualités qu'il a
  lui-même créées depuis le site (vérifié via le champ technique
  `cree_par` sur `NewsPage`). Les boutons Modifier/Supprimer n'apparaissent
  que sur ses propres actualités, sur la page de l'article et dans la liste.
- **Depuis l'admin Wagtail** (`/admin/`) : un éditeur dispose du CRUD
  complet natif de Wagtail sur **toutes** les actualités, y compris celles
  créées depuis le site — créer, modifier, supprimer, consulter (aperçu et
  historique des révisions). Aucune duplication dans l'admin Django
  (`/django-admin/`) n'a été ajoutée pour ce modèle : les pages Wagtail
  (arborescence, révisions, permissions par groupe) sont gérées de façon
  fiable uniquement depuis l'admin Wagtail, qui couvre déjà entièrement ce
  besoin.
- Le formulaire simplifié du site (contenu = un seul champ texte) ne
  restitue, lors d'une modification, que les blocs "paragraphe" du contenu
  existant : une actualité enrichie depuis l'admin Wagtail avec d'autres
  types de blocs (citation, image dans le corps, encart...) doit être
  modifiée depuis l'admin Wagtail plutôt que depuis le site public, sous
  peine de perdre cette mise en forme avancée.

## Sections dynamiques de la page d'accueil

Juste après le texte d'introduction, la page d'accueil peut afficher deux
sections automatiques, chacune contrôlée par un interrupteur dans l'admin
Wagtail (édition de la page d'accueil) — **et qui ne s'affiche de toute
façon que s'il y a effectivement quelque chose à montrer** :

- **Dernière actualité** : affiche la plus récente actualité publiée au
  cours des **30 derniers jours**. Si aucune actualité n'a été publiée
  récemment, la section n'apparaît pas du tout, même si l'interrupteur est activé.
- **Prochaines activités** : affiche les **5 premières activités à venir**
  du calendrier (`calendrier` app), à partir de la date du jour, sur un
  fond coloré avec une image de fond (idéalement une image évoquant un
  agenda/calendrier, à choisir dans le champ "Image de fond de la section
  'Prochaines activités'"). N'apparaît que s'il existe au moins une
  activité à venir.

Ces deux interrupteurs se trouvent dans l'admin Wagtail, en éditant la page
d'accueil, sous "Sections dynamiques (actualité récente & prochaines activités)".

Toujours en éditant la page d'accueil, la liste **"Sections en défilement"**
permet d'ajouter autant de blocs que voulu, affichés après les deux
sections précédentes. Pour chaque bloc, un champ **"Type de section"**
permet de choisir entre :
- **Défilement normal** : image (à gauche, à droite ou en pleine largeur en
  fond) + texte — comme avant ;
- **Colonnes (1 à 3)** : titre de section facultatif + 1 à 3 colonnes,
  chacune avec son propre titre, texte et image facultative.

Chaque bloc, quel que soit son type, dispose aussi d'un champ **"Liens"**
commun : vous pouvez y ajouter autant de liens que voulu (texte + adresse),
au moins deux si besoin — affichés comme des boutons à la suite les uns des
autres, aussi bien pour une section en défilement normal que pour une
section en colonnes.

Les deux types de blocs peuvent être mélangés et réordonnés librement dans
la même liste (glisser-déposer dans l'admin Wagtail) : ce sont tous des
éléments de la même séquence en défilement continu. Contrairement aux deux
sections dynamiques ci-dessus, ces blocs sont toujours affichés tels que
configurés (pas de condition automatique de contenu).

## Application "calendrier" (activités & réservations de salle)

Cette application est un module Django classique (pas une page Wagtail) :
elle est accessible à l'adresse `/calendrier/` et un lien "Réservations" est
automatiquement ajouté au menu principal du site. Elle ne dépend d'aucun
service externe (pas de synchronisation avec un agenda tiers) : toutes les
données sont stockées et gérées directement sur le site.

**Fonctionnement**

- Le calendrier affiche un mois à la fois, avec navigation par les flèches
  précédent/suivant ou par les listes déroulantes mois/année.
- Chaque activité et chaque réservation couvre une **fourchette de dates**
  (date de début / date de fin, sans horaire) : pour un événement d'un
  seul jour, laissez simplement les deux dates identiques. Une activité ou
  réservation qui s'étend sur plusieurs jours apparaît sur chacune des
  cases correspondantes du calendrier.
- Chaque activité affichée dans une case du calendrier est cliquable et mène
  à sa page de détail.
- Cliquer sur une case **vide** du calendrier (ou sur le bouton d'ajout) :
  - ouvre le formulaire **d'ajout d'activité** si vous êtes connecté,
  - ouvre le formulaire **de demande de réservation de salle** sinon
    (aucune connexion requise).
- Une **activité** peut être publique (visible par tous) ou privée (visible
  uniquement par les personnes connectées). Une couleur lui est attribuée
  automatiquement selon sa visibilité (modifiable dans le formulaire).
- **Modifier ou supprimer une activité** : depuis sa page de détail (ou
  directement depuis la case du calendrier), l'auteur de l'activité ou un
  administrateur voit des boutons "Modifier" et "Supprimer". La suppression
  demande une confirmation.
- Une **demande de réservation** reste "en attente" tant qu'un administrateur
  ne l'a pas traitée. Une fois **validée**, la case correspondante du
  calendrier affiche automatiquement "Salle réservée" pour tous les
  visiteurs (sans jamais révéler les coordonnées du demandeur à un
  non-administrateur) — aucune activité séparée n'est créée, c'est la
  réservation elle-même qui s'affiche.
- **Modifier ou supprimer une réservation** : comme pour une activité, un
  administrateur peut modifier les coordonnées/dates d'une réservation
  (bouton "Modifier" sur sa page de détail ou dans la liste des demandes)
  ou la supprimer définitivement — y compris une fois déjà validée
  (la case "Salle réservée" disparaît alors du calendrier).
- Les administrateurs (`is_staff`) disposent d'une page dédiée
  **Gérer les demandes de réservation** (`/calendrier/reservations/`), avec
  boutons Valider / Refuser / Modifier, et voient l'intégralité des
  informations dans le calendrier (coordonnées, statuts).
- Une interface d'administration Django classique est disponible dans
  `/django-admin/` (distincte de l'admin Wagtail `/admin/`), avec actions
  groupées de validation/refus des réservations.

**Contrat de location (PDF)**

Une fois une réservation **validée**, sa fiche de détail propose un bouton
**"Rédiger le contrat de location"**. Le formulaire ne demande que les
informations propres au contrat (le locataire et les dates sont déjà
connus, repris automatiquement de la réservation) :
- Prénom et nom de la personne qui gère la location pour le compte de
  l'ASBL (le "délégué").
- Les locaux pris en charge par la location (cases à cocher : salle des
  fêtes et scène, local café, cuisine équipée, sanitaires).
- Le montant de la location et le montant de la caution.

À la validation, un PDF complet est généré — nommé `Contrat de location -
Nom Prénom - date de début.pdf` — puis proposé en téléchargement
immédiat. Ce PDF combine :
- les pages variables du contrat (identité des parties, dates, locaux,
  montants, articles 1 à 12), générées à partir du texte du contrat-type
  de l'ASBL (`calendrier/contrats.py`) ;
- les annexes fixes (Annexe I : mobilier, Annexe II : vaisselle, Annexe
  III : conditions bruit), reprises telles quelles depuis le document
  modèle d'origine (`calendrier/data/CONTRAT_DE_LOCATION_template.pdf`),
  qui n'est pas un PDF à champs remplissables.

Un contrat déjà généré pour une réservation reste modifiable (le formulaire
se rouvre pré-rempli) : l'enregistrer régénère le PDF et remplace le
précédent. Le fichier généré reste aussi téléchargeable à tout moment
depuis la fiche de la réservation (stocké dans `media/contrats_location/`).

**Comptes utilisateurs**

- Créez un compte "membre" avec `python manage.py createsuperuser` (ou via
  `/django-admin/` une fois connecté) pour tester l'ajout d'activités.
- Cochez la case **Statut équipe technique (is_staff)** sur un compte dans
  `/django-admin/auth/user/` pour lui donner les droits d'administration
  des réservations.
- Connexion : `/connexion/` — Déconnexion : `/deconnexion/`.

## Application "theatre" (gestion des places de théâtre) — site secondaire

Cette application est un **site secondaire complet**, intégré tel quel
depuis un projet Django autonome préexistant (représentations, réservations,
plan de salle avec placement automatique, contrôle d'entrée / tickets,
ventes flash, zone tampon pour replacer une réservation) : ce n'est pas une
page Wagtail, elle a sa propre interface (Bootstrap, chargé depuis un CDN)
et son propre design, différent du reste du site — voulu ainsi puisqu'il
s'agit d'un outil de gestion interne plutôt que d'une page publique.

- **Accès** : `/theatre/`. Toutes ses pages exigent d'être connecté (elle
  réutilise le système de connexion du site principal — `/connexion/` —,
  aucun compte séparé n'est nécessaire).
- **Lien de retour** : un lien "← Retour au site principal" a été ajouté
  dans son menu, vers la page d'accueil du site (`/`).
- **Lien dans le menu principal** : un lien "Théâtre" est ajouté
  automatiquement dans le menu du site (comme le lien "Réservations"),
  mais **uniquement visible par les visiteurs connectés** — un visiteur
  anonyme ne le voit pas du tout. Ce lien est géré dans le code
  (`templates/base.html`), pas via le snippet "Menu principal" : pour le
  retirer ou changer son libellé, il faut modifier ce fichier.
- **Administration Django classique** (`/django-admin/`) : toutes les
  données (représentations, réservations, tickets, ventes flash...) y sont
  aussi gérables, comme pour l'app `calendrier`.

⚠️ Cette application est montée sur le chemin `/theatre/`, en dehors de
l'arborescence Wagtail : ne créez pas de page Wagtail avec le slug
"theatre" au premier niveau du site, elle serait inaccessible (ce chemin
étant intercepté avant que Wagtail ne puisse le servir).

**Droits d'accès** : l'accès à l'application est réservé aux utilisateurs
connectés disposant explicitement de la permission Django dédiée
**"Peut accéder à l'application Théâtre"** (`theatre.acces_application`).

- Un visiteur non connecté est redirigé vers la page de connexion du site.
- Un utilisateur connecté mais **sans cette permission** reçoit une page
  d'erreur 403 (accès interdit).
- Les **super-utilisateurs** ont toujours accès, quelle que soit cette
  permission (comportement natif de Django).
- Le lien "Théâtre" du menu principal du site n'apparaît lui-même que pour
  les utilisateurs disposant de cette permission (`{% if perms.theatre.acces_application %}`
  dans `templates/base.html`) : un utilisateur non autorisé ne voit donc
  même pas ce lien, plutôt que de tomber sur une erreur en cliquant dessus.

**Pour autoriser ou retirer l'accès à un utilisateur**, dans l'admin
Django (`/django-admin/`) :
1. *Authentification et autorisation → Utilisateurs* → ouvrez la fiche de
   la personne concernée.
2. Section **"Permissions utilisateur"** : dans la liste "Permissions
   disponibles", recherchez `theatre | acces application | Peut accéder à
   l'application Théâtre`.
3. Ajoutez-la à la liste "Permissions choisies" pour autoriser l'accès (ou
   retirez-la pour le révoquer), puis enregistrez.

Pour autoriser plusieurs utilisateurs d'un coup, créez un **groupe**
(*Authentification et autorisation → Groupes*) avec cette même permission,
puis ajoutez-y les utilisateurs concernés (*Utilisateurs → section
"Groupes"*) : ils héritent alors tous de l'accès via ce groupe.

Cette permission est déclarée sur un modèle technique sans données propres
(`AccesApplication` dans `theatre/models.py`) : c'est la façon standard de
créer une permission Django "globale" non liée à un modèle métier précis.

## Référencement (SEO)

Le module [wagtail-seo](https://docs.coderedcorp.com/wagtail-seo/) est
intégré au site : chaque page (accueil, actualités, médias, infos, contact)
dispose d'un onglet **Promotion** enrichi dans l'admin Wagtail, avec :

- Titre et description SEO (avec valeurs de repli automatiques si laissés
  vides : titre de la page, résumé...)
- Image de partage (Open Graph / Twitter Card)
- URL canonique
- Données structurées Schema.org (JSON-LD), y compris un type "Article"
  pour les actualités (meilleur référencement sur Google Actualités / réseaux
  sociaux)

**Réglages du site** (organisation, logo, réseaux sociaux, image de partage
par défaut...) : nouvel onglet **SEO** dans *Paramètres* de l'admin Wagtail
— apparu automatiquement avec l'installation du module, aucune donnée pré-
remplie : à compléter une fois après la mise en production.

Techniquement : chaque modèle de page hérite maintenant de `SeoMixin`
(voir `home/models.py`, `news/models.py`, `info/models.py`,
`contact/models.py`, `media_gallery/models.py`), et `templates/base.html`
inclut les gabarits fournis par le module (`wagtailseo/meta.html` dans le
`<head>`, `wagtailseo/struct_data.html` et, sur la page d'accueil
uniquement, `wagtailseo/struct_org_data.html` en fin de `<body>`). Les
pages hors arborescence Wagtail (calendrier, recherche, connexion...)
continuent d'utiliser les balises `<title>`/`<meta description>` manuelles
d'origine, puisque wagtail-seo n'a rien à afficher en l'absence d'une page
Wagtail dans le contexte.

## Application "page_libre" (pages libres)

Une **page libre** (`page_libre` app) est un type de page Wagtail créable
**n'importe où** dans l'arborescence du site, sans lien automatique avec le
menu principal — utile pour une page ponctuelle (campagne, affiche, QR
code, page liée depuis un article...). Rien n'empêche un administrateur de
l'ajouter manuellement au menu (*Snippets > Menu principal*) s'il le
souhaite : ce n'est simplement pas fait automatiquement.

Chaque page libre propose, dans l'admin Wagtail :

1. **Logo et titres** : logo facultatif, titre affiché (sinon le titre de
   la page est utilisé) et sous-titre facultatif.
2. **Sections en défilement** (autant que voulu) : le même système que la
   page d'accueil — pour chaque section, choix entre une mise en page
   **simple** (image + texte + liens) ou **en colonnes** (1 à 3, chacune
   avec sa propre image et son propre texte, liens communs à la section).
   Ce système est partagé avec la page d'accueil via une classe abstraite
   commune (`SectionDefilementAbstraite` dans `home/models.py`) : toute
   amélioration future de ce système profite aux deux à la fois.
3. **Galerie de miniatures** (titre facultatif) : autant de miniatures que
   voulu, affichées sur une grille de **4 colonnes** (2 colonnes sur
   tablette, 1 sur mobile) ; cliquer sur une miniature l'ouvre en grand
   format dans une boîte de type lightbox (réutilise le même script que la
   galerie photos de l'app `media_gallery`). N'apparaît pas du tout si
   aucune miniature n'est ajoutée.

## Liens vers une page du site (app "info")

Dans le contenu par blocs de la page Infos (et, par ricochet, des articles
d'actualité qui réutilisent le même bloc "Lien utile"), un lien peut
maintenant pointer vers **n'importe quelle page du site**, via un
sélecteur de page dans l'admin Wagtail — plus seulement vers une adresse
externe. Si une page est choisie, elle est prioritaire sur l'URL externe
éventuellement renseignée en dessous.

## Personnalisation graphique

Les couleurs et polices sont centralisées en variables CSS en haut de
`static/css/main.css` (`--color-primary`, `--color-accent`, `--font-heading`…) :
il suffit de les modifier pour adapter la charte graphique.
