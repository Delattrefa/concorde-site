# Manuel d'utilisation — sources

Sources des deux manuels PDF :
- `docs/Manuel d'utilisation - Site La Concorde.pdf` : manuel complet, destiné
  aux responsables de l'ASBL (`manuel.html`) ;
- `docs/Manuel des membres - Site La Concorde.pdf` : manuel des simples
  membres (`manuel-membres.html`) : compte, calendrier, planning, actualités.

```
docs/manuel/
├── manuel.html            # le texte du manuel complet
├── manuel-membres.html    # le texte du manuel des membres
├── manuel.css             # mise en page A4 commune aux deux manuels
├── img/                   # captures d'écran en JPEG, référencées par manuel.html
│   └── couverture.jpg     # photo de couverture (pas une capture : à garder)
└── outils/
    ├── preparer.sh        # site de démonstration sur une copie de la base
    ├── reglages_manuel.py # réglages Django de ce site de démonstration
    ├── donnees_demo.py    # comptes et données fictives des captures
    ├── captures.py        # captures d'écran (Playwright + Chrome)
    └── rendu.py           # conversion HTML → PDF (Chrome)
```

## Modifier seulement le texte

1. Éditer `manuel.html`. Les figures sont numérotées automatiquement ;
   pour ajouter une image : `<figure><img src="img/nom.jpg"><figcaption>…</figcaption></figure>`
   (classes `basse`, `haute`, `mobile` sur `<figure>` pour régler la hauteur,
   `<div class="duo">` pour deux images côte à côte).
2. Régénérer le PDF (voir « Outils » ci-dessous) :
   ```bash
   docs/manuel/.outils-venv/bin/python docs/manuel/outils/rendu.py           # manuel complet
   docs/manuel/.outils-venv/bin/python docs/manuel/outils/rendu.py membres   # manuel des membres
   ```
   Les deux manuels partagent les mêmes captures : après une évolution de
   l'interface, régénérez les deux.

## Refaire les captures d'écran

Après une évolution de l'interface :

```bash
# Terminal 1 : site de démonstration (Ctrl+C pour l'arrêter)
docs/manuel/outils/preparer.sh

# Terminal 2 : toutes les captures, ou seulement certaines
docs/manuel/.outils-venv/bin/python docs/manuel/outils/captures.py
docs/manuel/.outils-venv/bin/python docs/manuel/outils/captures.py theatre_plan admin_paiements

# Puis le PDF
docs/manuel/.outils-venv/bin/python docs/manuel/outils/rendu.py
```

`preparer.sh` copie `src/db.sqlite3` dans `docs/manuel/.travail/` (ignoré par
Git) et y ajoute les données fictives : **la base de développement n'est
jamais modifiée**. Les dossiers de `src/media/` sont reliés par des liens
symboliques : le site de démonstration peut donc y créer des miniatures
d'images (fichiers de cache, sans conséquence).

Comptes de démonstration (mot de passe `Manuel2026!`) :

| Compte        | Profil                                          |
|---------------|-------------------------------------------------|
| `secretariat` | super-utilisateur (Marie Dupont)                |
| `membre`      | membre simple avec l'accès Théâtre (Paul Lambert) |

Les captures dépendent du contenu de `src/db.sqlite3` (pages, actualités,
albums, activités du calendrier de novembre–décembre 2026) : avec une autre
base, vérifier le résultat et adapter les adresses dans `captures.py`.

## Outils

Les outils tournent dans un environnement Python séparé de celui du site
(pas besoin de les installer sur le serveur), et utilisent le Google Chrome
installé sur le poste :

```bash
python3 -m venv docs/manuel/.outils-venv
docs/manuel/.outils-venv/bin/pip install playwright pillow
```

`captures.py` utilise aussi `pdftoppm` (paquet `poppler-utils`) pour mettre
en image les pages du contrat de location d'exemple.
