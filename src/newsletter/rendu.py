"""
Rendu HTML d'une newsletter pour les messageries.

Les messageries (Gmail, Outlook, Apple Mail...) ignorent une bonne partie du
CSS du web : la mise en page utilise donc des tableaux, des largeurs fixes
et des styles écrits directement sur chaque balise (styles « en ligne »).
Une petite feuille <style> complète le tout pour l'affichage sur mobile
dans les messageries qui la comprennent.

Le HTML est produit une fois par envoi, puis personnalisé pour chaque
destinataire (prénom, lien de désinscription) par simple remplacement.
"""
import html as html_module
import re

# Charte du site (static/css/main.css)
COULEURS = {
    "bordeaux": "#7a1f2b",
    "bordeaux_fonce": "#5a161f",
    "dore": "#d4af37",
    "texte": "#2b2222",
    "texte_doux": "#6b5c5c",
    "fond": "#f1e9e2",
    "carte": "#ffffff",
    "filet": "#e6dcd2",
}
POLICE_TEXTE = "Arial, Helvetica, sans-serif"
POLICE_TITRE = "Georgia, 'Times New Roman', serif"
LARGEUR_CONTENU = 536   # largeur utile dans une colonne de 600 px (marges de 32 px)

JETON_DESINSCRIPTION = "%%DESINSCRIPTION%%"
JETON_PRENOM = "{prenom}"


# ---------------------------------------------------------------------------
# Fonctions de texte (sans dépendance à Django)
# ---------------------------------------------------------------------------
STYLES_BALISES = {
    "p": f"margin:0 0 16px 0;font-family:{POLICE_TEXTE};font-size:16px;line-height:1.6;color:{COULEURS['texte']};",
    "h2": f"margin:24px 0 12px 0;font-family:{POLICE_TITRE};font-size:24px;line-height:1.3;color:{COULEURS['bordeaux_fonce']};font-weight:bold;",
    "h3": f"margin:20px 0 10px 0;font-family:{POLICE_TITRE};font-size:20px;line-height:1.3;color:{COULEURS['bordeaux_fonce']};font-weight:bold;",
    "h4": f"margin:16px 0 8px 0;font-family:{POLICE_TEXTE};font-size:17px;line-height:1.4;color:{COULEURS['texte']};font-weight:bold;",
    "ul": "margin:0 0 16px 0;padding:0 0 0 24px;",
    "ol": "margin:0 0 16px 0;padding:0 0 0 24px;",
    "li": f"margin:0 0 6px 0;font-family:{POLICE_TEXTE};font-size:16px;line-height:1.6;color:{COULEURS['texte']};",
    "a": f"color:{COULEURS['bordeaux']};text-decoration:underline;",
    "blockquote": f"margin:0 0 16px 0;padding:8px 16px;border-left:4px solid {COULEURS['dore']};color:{COULEURS['texte_doux']};",
    "b": "font-weight:bold;",
    "strong": "font-weight:bold;",
}

_RE_BALISE = re.compile(r"<(p|h2|h3|h4|ul|ol|li|a|blockquote|b|strong)(\s[^>]*)?>", re.IGNORECASE)
_RE_ATTR_STYLE = re.compile(r"""\sstyle\s*=\s*(["'])(.*?)\1""", re.IGNORECASE | re.DOTALL)
_RE_DATA_ATTR = re.compile(r"""\sdata-[\w-]+\s*=\s*(["']).*?\1""", re.IGNORECASE | re.DOTALL)
_RE_HREF = re.compile(r"""(\shref\s*=\s*)(["'])(/[^"']*)\2""", re.IGNORECASE)


def styler_html(fragment, url_absolue=lambda u: u, styles=None):
    """Ajoute les styles en ligne aux balises d'un fragment HTML de texte
    riche, retire les attributs data-* et rend les liens absolus."""
    styles = {**STYLES_BALISES, **(styles or {})}

    def remplacer(m):
        balise = m.group(1).lower()
        attributs = _RE_DATA_ATTR.sub("", m.group(2) or "")
        style_existant = _RE_ATTR_STYLE.search(attributs)
        if style_existant:
            attributs = _RE_ATTR_STYLE.sub("", attributs)
            style = styles[balise] + style_existant.group(2)
        else:
            style = styles[balise]
        if balise == "a" and "target=" not in attributs:
            attributs += ' target="_blank"'
        return f'<{balise}{attributs} style="{style}">'

    fragment = _RE_BALISE.sub(remplacer, fragment or "")
    return _RE_HREF.sub(lambda m: f"{m.group(1)}{m.group(2)}{url_absolue(m.group(3))}{m.group(2)}", fragment)


def html_vers_texte(contenu_html):
    """Version texte brut d'un e-mail HTML (partie « text/plain » du message,
    lue par les messageries qui n'affichent pas le HTML et appréciée des
    filtres anti-spam)."""
    texte = re.sub(r"(?is)<(head|style|script)\b.*?</\1>", "", contenu_html)
    texte = re.sub(r'(?is)<span[^>]*class="preheader"[^>]*>.*?</span>', "", texte)
    # Liens : « texte (adresse) »
    texte = re.sub(
        r"""(?is)<a\b[^>]*href\s*=\s*(["'])(.*?)\1[^>]*>(.*?)</a>""",
        lambda m: (
            f"{re.sub(r'<[^>]+>', '', m.group(3)).strip()} ({m.group(2)})"
            if m.group(2) and not m.group(2).startswith("#") else m.group(3)
        ),
        texte,
    )
    texte = re.sub(r"(?i)<br\s*/?>", "\n", texte)
    texte = re.sub(r"(?i)<li\b[^>]*>", "\n - ", texte)
    texte = re.sub(r"(?i)</(p|h1|h2|h3|h4|tr|table|div|ul|ol|blockquote)>", "\n\n", texte)
    texte = re.sub(r"(?i)<hr\b[^>]*>", "\n----------\n", texte)
    texte = re.sub(r"<[^>]+>", "", texte)
    texte = html_module.unescape(texte).replace("\xa0", " ")
    lignes = [re.sub(r"[ \t]+", " ", ligne).strip() for ligne in texte.splitlines()]
    texte = "\n".join(lignes)
    return re.sub(r"\n{3,}", "\n\n", texte).strip() + "\n"


def personnaliser(contenu, prenom="", url_desinscription=""):
    """Remplace les jetons personnels (prénom, lien de désinscription) dans
    le HTML ou le texte d'une newsletter rendue."""
    if prenom:
        contenu = contenu.replace(JETON_PRENOM, html_module.escape(prenom.strip()))
    else:
        # « Bonjour {prenom}, » devient « Bonjour, »
        contenu = re.sub(r"[ \xa0]*\{prenom\}", "", contenu)
    return contenu.replace(JETON_DESINSCRIPTION, url_desinscription)


def hauteur_proportionnelle(largeur_origine, hauteur_origine, largeur_affichee):
    if not largeur_origine:
        return None
    return round(hauteur_origine * largeur_affichee / largeur_origine)


# ---------------------------------------------------------------------------
# Rendu complet (utilise Django et Wagtail)
# ---------------------------------------------------------------------------
def _image(image, largeur_affichee, alt=""):
    """Données d'une image pour l'e-mail : rendu deux fois plus large que
    l'affichage (écrans haute définition), adresse absolue, hauteur calculée."""
    from .models import url_absolue

    # PNG/GIF restent en PNG (transparence d'un logo) ; le reste en JPEG,
    # lu par toutes les messageries (Outlook ne lit pas le WebP).
    nom = (getattr(image.file, "name", "") or "").lower()
    format_sortie = "format-png" if nom.endswith((".png", ".gif")) else "format-jpeg|jpegquality-80"
    rendu = image.get_rendition(f"width-{largeur_affichee * 2}|{format_sortie}")
    largeur = min(largeur_affichee, rendu.width)
    return {
        "url": url_absolue(rendu.url),
        "largeur": largeur,
        "hauteur": hauteur_proportionnelle(rendu.width, rendu.height, largeur),
        "alt": alt or getattr(image, "description", "") or image.title,
    }


def _texte_riche(valeur):
    from wagtail.rich_text import expand_db_html

    from .models import url_absolue

    source = getattr(valeur, "source", valeur) or ""
    return styler_html(expand_db_html(source), url_absolue)


def _url_page(page):
    from .models import url_absolue

    return url_absolue(page.specific.url or "")


def _resume_page(page):
    """Résumé d'une page : description SEO, intro ou extrait."""
    specifique = page.specific
    for champ in ("search_description", "intro", "description", "hero_subtitle"):
        valeur = getattr(specifique, champ, "") or ""
        valeur = re.sub(r"<[^>]+>", " ", str(valeur)).strip()
        if valeur:
            return html_module.unescape(re.sub(r"\s+", " ", valeur))[:300]
    return ""


def _image_page(page):
    specifique = page.specific
    for champ in ("featured_image", "hero_image", "image_bandeau", "cover_image", "og_image"):
        image = getattr(specifique, champ, None)
        if image is not None:
            return image
    return None


def _preparer_blocs(newsletter):
    from datetime import date

    from news.models import NewsPage

    from .models import url_absolue

    blocs = []
    for bloc in newsletter.contenu:
        t, v = bloc.block_type, bloc.value

        if t == "titre":
            blocs.append({"type": "titre", "texte": v})

        elif t == "texte":
            blocs.append({"type": "texte", "html": _texte_riche(v)})

        elif t == "image":
            largeur = {"pleine": LARGEUR_CONTENU, "moyenne": 400, "petite": 260}.get(v["largeur"], LARGEUR_CONTENU)
            blocs.append({
                "type": "image",
                "image": _image(v["image"], largeur, v.get("alt")),
                "legende": v.get("legende"),
                "lien": v.get("lien") or "",
            })

        elif t == "bouton":
            url = _url_page(v["page"]) if v.get("page") else url_absolue(v.get("url") or "")
            dore = v.get("style") != "bordeaux"
            blocs.append({
                "type": "bouton", "texte": v["texte"], "url": url,
                "fond": COULEURS["dore"] if dore else COULEURS["bordeaux"],
                "couleur": "#1a1414" if dore else "#ffffff",
            })

        elif t == "actualites":
            actualites = (
                NewsPage.objects.live().public()
                .filter(date__lte=date.today())
                .order_by("-date", "-first_published_at")[: v.get("nombre") or 3]
            )
            elements = []
            for actu in actualites:
                elements.append({
                    "titre": actu.title,
                    "url": _url_page(actu),
                    "date": actu.date.strftime("%d/%m/%Y") if actu.date else "",
                    "resume": (actu.intro or _resume_page(actu))[:220],
                    "image": _image(actu.featured_image, 160, actu.title) if actu.featured_image else None,
                })
            if elements:
                blocs.append({"type": "actualites", "titre": v.get("titre"), "elements": elements})

        elif t == "page_en_avant":
            page = v["page"]
            image = v.get("image") or _image_page(page)
            blocs.append({
                "type": "page_en_avant",
                "titre": v.get("titre") or page.title,
                "texte": v.get("texte") or _resume_page(page),
                "image": _image(image, LARGEUR_CONTENU) if image else None,
                "url": _url_page(page),
                "texte_bouton": v.get("texte_bouton") or "En savoir plus",
            })

        elif t == "encadre":
            blocs.append({"type": "encadre", "titre": v.get("titre"), "html": _texte_riche(v["texte"])})

        elif t == "separateur":
            blocs.append({"type": "separateur"})

    return blocs


def rendre_newsletter(newsletter):
    """Renvoie (html, texte) de la newsletter, avec les jetons personnels
    non remplacés (voir personnaliser)."""
    from django.conf import settings
    from django.template.loader import render_to_string
    from django.urls import reverse

    from .models import url_absolue

    contexte = {
        "newsletter": newsletter,
        "objet": newsletter.objet,
        "preheader": newsletter.preheader,
        "salutation": newsletter.salutation,
        "blocs": _preparer_blocs(newsletter),
        "c": COULEURS,
        "police_texte": POLICE_TEXTE,
        "police_titre": POLICE_TITRE,
        "url_site": url_absolue("/"),
        "url_navigateur": url_absolue(reverse("newsletter:lire", args=[newsletter.pk])) if newsletter.pk else "",
        "url_desinscription": JETON_DESINSCRIPTION,
        "nom_expediteur": getattr(settings, "NEWSLETTER_NOM_EXPEDITEUR", "La Concorde asbl"),
        "adresse_postale": getattr(
            settings, "NEWSLETTER_ADRESSE_POSTALE", "Rue Émile Cornez 11 — 7387 Angre (Honnelles), Belgique"
        ),
    }
    contenu_html = render_to_string("newsletter/email/newsletter.html", contexte)
    return contenu_html, html_vers_texte(contenu_html)
