"""
Éditeur d'actualités du site : conversion entre le contenu de l'article
(StreamField « body » de NewsPage) et les blocs manipulés par l'éditeur
JavaScript du formulaire (static/news/js/editeur.js).

L'éditeur envoie une liste JSON de blocs { "type": …, "value": … }. Le texte
enrichi qu'il contient vient du navigateur : il est entièrement reconstruit
par NettoyeurTexteEnrichi, qui ne garde que les balises autorisées dans
Wagtail (paragraphes, intertitres, gras, italique, listes, liens).
"""
import json
from html import escape
from html.parser import HTMLParser

from django.core.exceptions import ValidationError
from wagtail.images import get_image_model
from wagtail.rich_text import expand_db_html

# Types de blocs proposés par l'éditeur du site. L'ancien bloc « image »
# (sans position) est converti en « image_positionnee » pleine largeur.
TYPES_EDITEUR = {"heading", "paragraph", "image_positionnee", "quote", "callout", "useful_link"}

FORMAT_APERCU = "max-400x300"


class NettoyeurTexteEnrichi(HTMLParser):
    """Reconstruit un texte enrichi sûr au format Wagtail à partir du HTML
    produit par le navigateur : balises hors liste supprimées (leur texte
    est gardé), attributs supprimés sauf l'adresse des liens, texte libre
    rangé dans des paragraphes."""

    RENOMMAGES = {"strong": "b", "em": "i", "div": "p", "h1": "h2", "h4": "h3", "h5": "h3", "h6": "h3"}
    BLOCS = {"p", "h2", "h3", "ul", "ol", "li"}
    EN_LIGNE = {"b", "i", "a"}
    IGNORES = {"script", "style", "template", "noscript"}
    PROTOCOLES_LIENS = ("http://", "https://", "mailto:", "tel:", "/")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.morceaux = []
        # Balises ouvertes ; « -a », « -p » : balise ignorée (lien refusé,
        # paragraphe dans un élément de liste), gardée pour sa fermeture.
        self.pile = []
        self.paragraphe_auto = False
        self.dans_ignore = 0

    # -- outils ------------------------------------------------------------
    def _ouvrir_paragraphe_auto(self):
        """Du texte (ou du gras, un lien…) hors de tout bloc : on l'entoure
        d'un paragraphe."""
        if not any(t in self.BLOCS for t in self.pile):
            self.morceaux.append("<p>")
            self.pile.append("p")
            self.paragraphe_auto = True

    def _fermer_jusqua(self, balise):
        while self.pile:
            ouverte = self.pile.pop()
            if not ouverte.startswith("-"):
                self.morceaux.append(f"</{ouverte}>")
            if ouverte == balise:
                break

    # -- analyse -----------------------------------------------------------
    def handle_starttag(self, balise, attributs):
        if balise in self.IGNORES:
            self.dans_ignore += 1
            return
        if self.dans_ignore:
            return
        balise = self.RENOMMAGES.get(balise, balise)

        if balise == "br":
            self._ouvrir_paragraphe_auto()
            self.morceaux.append("<br/>")
        elif balise in self.BLOCS:
            if balise == "li" and not any(t in ("ul", "ol") for t in self.pile):
                balise = "p"
            if balise == "p" and "li" in self.pile:
                self.pile.append("-p")
                return
            if balise != "li":
                # Un bloc ferme le bloc en cours (pas d'imbrication de blocs,
                # sauf les éléments de liste dans leur liste).
                while any(t in self.BLOCS for t in self.pile):
                    self._fermer_jusqua(next(t for t in reversed(self.pile) if t in self.BLOCS))
            elif "li" in self.pile:
                self._fermer_jusqua("li")
            self.paragraphe_auto = False
            self.morceaux.append(f"<{balise}>")
            self.pile.append(balise)
        elif balise in self.EN_LIGNE:
            self._ouvrir_paragraphe_auto()
            if balise == "a":
                href = (dict(attributs).get("href") or "").strip()
                if not href.lower().startswith(self.PROTOCOLES_LIENS) or href.startswith("//"):
                    self.pile.append("-a")
                    return
                self.morceaux.append(f'<a href="{escape(href)}">')
            else:
                self.morceaux.append(f"<{balise}>")
            self.pile.append(balise)

    def handle_startendtag(self, balise, attributs):
        if balise == "br":
            self.handle_starttag(balise, attributs)

    def handle_endtag(self, balise):
        if balise in self.IGNORES:
            self.dans_ignore = max(0, self.dans_ignore - 1)
            return
        if self.dans_ignore:
            return
        balise = self.RENOMMAGES.get(balise, balise)
        marqueur = "-" + balise
        if marqueur in self.pile and (balise not in self.pile or self.pile[::-1].index(marqueur) < self.pile[::-1].index(balise)):
            # Fin d'une balise ignorée : on retire seulement son marqueur.
            del self.pile[len(self.pile) - 1 - self.pile[::-1].index(marqueur)]
        elif balise in self.pile:
            self._fermer_jusqua(balise)

    def handle_data(self, texte):
        if self.dans_ignore:
            return
        if not self.pile and not texte.strip():
            return
        if self.pile and self.pile[-1] in ("ul", "ol"):
            if not texte.strip():
                return
            self.morceaux.append("<li>")
            self.pile.append("li")
        self._ouvrir_paragraphe_auto()
        self.morceaux.append(escape(texte, quote=False))

    def resultat(self):
        self.close()
        while self.pile:
            self._fermer_jusqua(self.pile[-1])
        html = "".join(self.morceaux)
        # Blocs vides laissés par l'éditeur (lignes vides, listes vides)
        for vide in ("<p></p>", "<p><br/></p>", "<h2></h2>", "<h3></h3>", "<li></li>", "<ul></ul>", "<ol></ol>"):
            while vide in html:
                html = html.replace(vide, "")
        return html.strip()


def nettoyer_texte_enrichi(html):
    nettoyeur = NettoyeurTexteEnrichi()
    nettoyeur.feed(html or "")
    return nettoyeur.resultat()


def apercu_image(image):
    return image.get_rendition(FORMAT_APERCU).url


# -- Du contenu de l'article vers l'éditeur ---------------------------------

def corps_vers_editeur(body):
    """Blocs de l'article sous la forme attendue par l'éditeur JavaScript.
    Le texte enrichi est « développé » (liens internes Wagtail → adresses)
    pour s'afficher tel quel dans l'éditeur."""
    blocs = []
    for bloc in body:
        valeur = bloc.value
        if bloc.block_type == "heading":
            blocs.append({"type": "heading", "value": valeur})
        elif bloc.block_type == "paragraph":
            blocs.append({"type": "paragraph", "value": expand_db_html(valeur.source)})
        elif bloc.block_type in ("image", "image_positionnee"):
            image = valeur if bloc.block_type == "image" else valeur["image"]
            if image is None:
                continue
            blocs.append({
                "type": "image_positionnee",
                "value": {
                    "image": image.pk,
                    "position": "pleine" if bloc.block_type == "image" else valeur["position"],
                    "legende": "" if bloc.block_type == "image" else valeur["legende"],
                },
                "apercu": apercu_image(image),
            })
        elif bloc.block_type == "quote":
            blocs.append({"type": "quote", "value": {"text": valeur["text"], "attribution": valeur["attribution"]}})
        elif bloc.block_type == "callout":
            texte = valeur["text"].source if valeur["text"] else ""
            blocs.append({"type": "callout", "value": {"title": valeur["title"], "text": expand_db_html(texte)}})
        elif bloc.block_type == "useful_link":
            # Pas de sélecteur de page sur le site : un lien vers une page du
            # site devient un lien par adresse.
            url = valeur["page"].full_url if valeur["page"] else valeur["url"]
            blocs.append({"type": "useful_link", "value": {"title": valeur["title"], "url": url or ""}})
    return blocs


# -- De l'éditeur vers le contenu de l'article ------------------------------

def _texte(valeur, longueur=None):
    texte = valeur.strip() if isinstance(valeur, str) else ""
    return texte[:longueur] if longueur else texte


def editeur_vers_corps(donnees_json, stream_block):
    """Contenu de l'article (StreamValue) à partir du JSON envoyé par
    l'éditeur. Lève ValidationError avec un message lisible si un bloc est
    incomplet (image manquante, lien sans adresse…)."""
    try:
        blocs = json.loads(donnees_json or "[]")
    except ValueError:
        raise ValidationError("Le contenu de l'article n'a pas pu être lu. Réessayez.")
    if not isinstance(blocs, list):
        raise ValidationError("Le contenu de l'article n'a pas pu être lu. Réessayez.")

    Image = get_image_model()
    brut = []
    for bloc in blocs:
        if not isinstance(bloc, dict) or bloc.get("type") not in TYPES_EDITEUR:
            continue
        type_bloc, valeur = bloc["type"], bloc.get("value")
        valeur_dict = valeur if isinstance(valeur, dict) else {}

        if type_bloc == "heading":
            if _texte(valeur):
                brut.append({"type": "heading", "value": _texte(valeur, 255)})
        elif type_bloc == "paragraph":
            texte = nettoyer_texte_enrichi(valeur if isinstance(valeur, str) else "")
            if texte:
                brut.append({"type": "paragraph", "value": texte})
        elif type_bloc == "image_positionnee":
            try:
                image_id = int(valeur_dict.get("image"))
            except (TypeError, ValueError):
                image_id = None
            if image_id is None or not Image.objects.filter(pk=image_id).exists():
                raise ValidationError("Un bloc image n'a pas de photo : choisissez-en une ou retirez le bloc.")
            position = valeur_dict.get("position")
            brut.append({"type": "image_positionnee", "value": {
                "image": image_id,
                "position": position if position in ("pleine", "gauche", "droite") else "pleine",
                "legende": _texte(valeur_dict.get("legende"), 255),
            }})
        elif type_bloc == "quote":
            if _texte(valeur_dict.get("text")):
                brut.append({"type": "quote", "value": {
                    "text": _texte(valeur_dict.get("text")),
                    "attribution": _texte(valeur_dict.get("attribution"), 255),
                }})
        elif type_bloc == "callout":
            titre = _texte(valeur_dict.get("title"), 255)
            texte = nettoyer_texte_enrichi(valeur_dict.get("text") if isinstance(valeur_dict.get("text"), str) else "")
            if titre or texte:
                brut.append({"type": "callout", "value": {"title": titre, "text": texte}})
        elif type_bloc == "useful_link":
            titre, url = _texte(valeur_dict.get("title"), 255), _texte(valeur_dict.get("url"))
            if not (titre or url):
                continue
            if not (titre and url):
                raise ValidationError("Un bloc « Lien utile » doit avoir un texte et une adresse.")
            brut.append({"type": "useful_link", "value": {"title": titre, "page": None, "url": url}})

    corps = stream_block.to_python(brut)
    try:
        stream_block.clean(corps)
    except ValidationError:
        raise ValidationError(
            "Un bloc du contenu est invalide (par exemple une adresse de lien "
            "incorrecte : elle doit commencer par https://)."
        )
    return corps
