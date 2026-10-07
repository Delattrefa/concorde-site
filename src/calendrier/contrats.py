"""
Génération du contrat de location de salle en PDF, à partir d'une
réservation validée et des informations complémentaires saisies dans
ContratLocationForm (délégué de l'ASBL, locaux pris en charge, montants).

Le PDF final est composé de deux parties :
1. Les pages du contrat, régénérées à chaque fois avec reportlab :
   identité des parties, puis les articles du contrat-type
   (modèle ArticleContrat, modifiables sur le site par les
   administrateurs), puis les signatures.
2. Les annexes PDF (modèle AnnexeContrat : mobilier, vaisselle,
   conditions particulières...), ajoutées telles quelles à la suite.
   Elles peuvent être remplacées par de nouveaux PDF sur le site.

Tant qu'aucune annexe n'a été enregistrée, les annexes d'origine sont
reprises du PDF modèle (calendrier/data/CONTRAT_DE_LOCATION_template.pdf).
"""
import io
import os
import re
from datetime import date

from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

CHEMIN_MODELE = os.path.join(os.path.dirname(__file__), "data", "CONTRAT_DE_LOCATION_template.pdf")

# Pages (0-indexées) du PDF modèle correspondant aux annexes fixes,
# reprises telles quelles à la suite des pages variables régénérées.
PREMIERE_PAGE_ANNEXES = 5  # page 6 du document (ANNEXE I)


def _mise_en_forme_date(une_date):
    """Formate une date en français, ex : '7 octobre 2026'."""
    mois_fr = [
        "", "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    return f"{une_date.day} {mois_fr[une_date.month]} {une_date.year}"



# ---------------------------------------------------------------------------
# Texte des articles : variables et mise en forme simple
# ---------------------------------------------------------------------------
VARIABLES_DISPONIBLES = {
    "locaux": "liste à puces des locaux cochés (à écrire seule sur sa ligne)",
    "date_debut": "premier jour de la location (ex : 7 octobre 2026)",
    "date_fin": "dernier jour de la location",
    "montant_location": "montant de la location, ex : 350,00",
    "montant_caution": "montant de la caution, ex : 150,00",
    "locataire": "prénom et nom du locataire",
    "delegue": "prénom et nom du délégué de l'ASBL",
}

AIDE_MISE_EN_FORME = (
    "Une ligne vide sépare deux paragraphes ; un simple retour à la ligne "
    "reste dans le même paragraphe. Une ligne commençant par « - » devient "
    "une puce. Entourer un passage de deux astérisques le met en gras : "
    "**texte**."
)

_RE_VARIABLE = re.compile(r"\{(\w+)\}")
_RE_GRAS = re.compile(r"\*\*(.+?)\*\*")


def variables_inconnues(texte):
    """Renvoie les noms entre accolades qui ne correspondent à aucune
    variable disponible (fautes de frappe), pour les signaler à la saisie."""
    return sorted({nom for nom in _RE_VARIABLE.findall(texte) if nom not in VARIABLES_DISPONIBLES})


def _montant(valeur):
    """150 → '150,00' (format belge)."""
    try:
        return f"{float(valeur):,.2f}".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return str(valeur)


def _valeurs_variables(reservation, contrat):
    return {
        "date_debut": _mise_en_forme_date(reservation.date_debut),
        "date_fin": _mise_en_forme_date(reservation.date_fin),
        "montant_location": _montant(contrat.montant_location),
        "montant_caution": _montant(contrat.montant_caution),
        "locataire": f"{reservation.prenom} {reservation.nom}",
        "delegue": f"{contrat.delegue_prenom} {contrat.delegue_nom}",
    }


def _ligne_en_balisage(ligne, valeurs):
    """Convertit une ligne de texte saisi en balisage reportlab : caractères
    spéciaux échappés, variables remplacées, **gras** converti."""
    ligne = escape(ligne)

    def remplacer(correspondance):
        nom = correspondance.group(1)
        if nom in valeurs:
            return escape(str(valeurs[nom]))
        return correspondance.group(0)

    ligne = _RE_VARIABLE.sub(remplacer, ligne)
    return _RE_GRAS.sub(r"<b>\1</b>", ligne)


def _texte_vers_elements(texte, valeurs, locaux, style):
    """Transforme le texte d'un article en éléments reportlab
    (paragraphes et listes à puces)."""
    elements = []
    texte = (texte or "").replace("\r\n", "\n").strip()

    for bloc in re.split(r"\n\s*\n", texte):
        lignes = []
        puces = []

        def vider_lignes():
            if lignes:
                elements.append(Paragraph("<br/>".join(lignes), style))
                lignes.clear()

        def vider_puces():
            if puces:
                elements.append(ListFlowable(
                    [ListItem(Paragraph(p, style)) for p in puces], bulletType="bullet",
                ))
                puces.clear()

        for ligne in bloc.split("\n"):
            propre = ligne.strip()
            if not propre:
                continue
            if propre == "{locaux}":
                vider_lignes()
                vider_puces()
                if locaux:
                    elements.append(ListFlowable(
                        [ListItem(Paragraph(escape(libelle), style)) for libelle in locaux],
                        bulletType="bullet",
                    ))
                else:
                    elements.append(Paragraph("(aucun local spécifiquement listé)", style))
            elif propre[:2] in ("- ", "• "):
                vider_lignes()
                puces.append(_ligne_en_balisage(propre[2:].strip(), valeurs))
            else:
                vider_puces()
                lignes.append(_ligne_en_balisage(propre, valeurs))

        vider_lignes()
        vider_puces()

    return elements


PIED_DE_PAGE = (
    "ASBL LA CONCORDE – Contrat de Location (conditions 2019) — "
    "Compte de la poste : BE 73 0000 9818 9460 - BIC : BPOTBEB - "
    "TVA BE 0412.730.545 — Tél : 065/75 01 75 - "
    "Adresse mail : infos@la-concorde.be - www.la-concorde.be"
)
HAUTEUR_BANDEAU = 46 * mm      # hauteur de l'image de fond d'en-tête (page 1)
MARGE_HAUTE = 22 * mm
MARGE_BASSE = 24 * mm          # place pour le pied de page
MARGE_LATERALE = 22 * mm


def _lire_image(fichier):
    """Contenu d'un fichier (FieldFile Django) sous forme d'ImageReader, ou None."""
    if not fichier:
        return None
    try:
        fichier.open("rb")
        try:
            return ImageReader(io.BytesIO(fichier.read()))
        finally:
            fichier.close()
    except (OSError, ValueError):
        return None


def _image_signature(signature, largeur_max=55 * mm, hauteur_max=22 * mm):
    """Flowable de l'image de signature (proportions conservées), ou None."""
    if signature is None:
        return None
    try:
        rendu = signature.get_rendition("max-800x400|format-png")
        lecteur = _lire_image(rendu.file)
    except Exception:
        lecteur = None
    if lecteur is None:
        return None
    largeur, hauteur = lecteur.getSize()
    echelle = min(largeur_max / largeur, hauteur_max / hauteur)
    rendu.file.open("rb")
    try:
        donnees = io.BytesIO(rendu.file.read())
    finally:
        rendu.file.close()
    image = Image(donnees, width=largeur * echelle, height=hauteur * echelle, mask="auto")
    image.hAlign = "LEFT"
    return image


def _dessiner_bandeau(canvas, image, eclaircir):
    """Image de fond de l'en-tête, en bandeau pleine largeur (recadrée pour
    remplir le bandeau, sans déformation)."""
    largeur_page, hauteur_page = A4
    larg_img, haut_img = image.getSize()
    echelle = max(largeur_page / larg_img, HAUTEUR_BANDEAU / haut_img)
    larg, haut = larg_img * echelle, haut_img * echelle
    x = (largeur_page - larg) / 2
    y = hauteur_page - HAUTEUR_BANDEAU - (haut - HAUTEUR_BANDEAU) / 2

    canvas.saveState()
    chemin = canvas.beginPath()
    chemin.rect(0, hauteur_page - HAUTEUR_BANDEAU, largeur_page, HAUTEUR_BANDEAU)
    canvas.clipPath(chemin, stroke=0, fill=0)
    canvas.drawImage(image, x, y, width=larg, height=haut, mask="auto")
    if eclaircir:
        canvas.setFillColor(colors.white)
        canvas.setFillAlpha(0.55)
        canvas.rect(0, hauteur_page - HAUTEUR_BANDEAU, largeur_page, HAUTEUR_BANDEAU, stroke=0, fill=1)
    canvas.restoreState()


def _dessiner_pied(canvas, doc, style_petit):
    """Pied de page identique sur chaque page du contrat."""
    canvas.saveState()
    pied = Paragraph(PIED_DE_PAGE, style_petit)
    largeur = A4[0] - 2 * MARGE_LATERALE
    _, hauteur = pied.wrap(largeur, 20 * mm)
    pied.drawOn(canvas, MARGE_LATERALE, 10 * mm)
    canvas.setStrokeColor(colors.HexColor("#cccccc"))
    canvas.setLineWidth(0.5)
    canvas.line(MARGE_LATERALE, 10 * mm + hauteur + 2 * mm, A4[0] - MARGE_LATERALE, 10 * mm + hauteur + 2 * mm)
    canvas.restoreState()


def _construire_pages_variables(reservation, contrat, articles, mise_en_page=None):
    """Construit, avec reportlab, les pages variables du contrat (identité
    des parties, puis chaque article actif du contrat-type, signatures) et
    renvoie le résultat en mémoire, sans fichier temporaire.

    Mise en page : un titre d'article n'est jamais laissé seul en bas de
    page, et le bloc des signatures reste sur la même page que la fin du
    dernier article."""

    tampon = io.BytesIO()
    doc = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        topMargin=MARGE_HAUTE,
        bottomMargin=MARGE_BASSE,
        leftMargin=MARGE_LATERALE,
        rightMargin=MARGE_LATERALE,
        title="Contrat de location — La Concorde asbl",
    )

    styles = getSampleStyleSheet()
    style_titre = ParagraphStyle(
        "TitreContrat", parent=styles["Title"], fontSize=19, leading=23, spaceAfter=12,
    )
    style_article = ParagraphStyle(
        "Article", parent=styles["Heading2"], fontSize=12.5, leading=16,
        spaceBefore=14, spaceAfter=6, keepWithNext=1,
    )
    style_normal = ParagraphStyle(
        "CorpsContrat", parent=styles["Normal"], fontSize=11, leading=15.5, spaceAfter=8,
        alignment=4,  # justifié
    )
    style_gauche = ParagraphStyle("CorpsGauche", parent=style_normal, alignment=0)
    style_coordonnees = ParagraphStyle(
        "Coordonnees", parent=styles["Normal"], fontSize=9.5, leading=13,
        textColor="#444444", alignment=1,
    )
    style_petit = ParagraphStyle(
        "PetitContrat", parent=styles["Normal"], fontSize=7.5, leading=10, textColor="#555555",
        alignment=1,
    )

    image_bandeau = None
    eclaircir = True
    if mise_en_page is not None:
        image_bandeau = _lire_image(mise_en_page.image_entete)
        eclaircir = mise_en_page.eclaircir_entete

    def premiere_page(canvas, doc_):
        if image_bandeau is not None:
            _dessiner_bandeau(canvas, image_bandeau, eclaircir)
        _dessiner_pied(canvas, doc_, style_petit)

    def pages_suivantes(canvas, doc_):
        _dessiner_pied(canvas, doc_, style_petit)

    elements = []

    # --- En-tête (dans le bandeau d'image s'il y en a une) -------------------
    elements.append(Paragraph("La Concorde asbl", style_titre))
    elements.append(Paragraph(
        "Rue Émile Cornez 11 — 7387 Angre/Honnelles — BE0412.730.545", style_coordonnees,
    ))
    if image_bandeau is not None:
        # Le contenu reprend sous le bandeau.
        elements.append(Spacer(1, HAUTEUR_BANDEAU - MARGE_HAUTE - 14 * mm))
    else:
        elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph("CONTRAT DE LOCATION", style_titre))

    # --- Parties -------------------------------------------------------------
    elements.append(Paragraph("<b>Entre les soussignés :</b>", style_normal))
    elements.append(Paragraph(
        f"{escape(reservation.prenom)} {escape(reservation.nom)}<br/>"
        f"Adresse : {escape(reservation.adresse)}<br/>"
        f"Téléphone : {escape(reservation.telephone)}<br/>"
        f"Mail : {escape(reservation.email)}<br/>"
        f"Ci-après dénommé(e) <b>client</b>,<br/>"
        f"D'UNE PART,",
        style_gauche,
    ))
    elements.append(Paragraph("Et", style_normal))
    elements.append(Paragraph(
        f"Monsieur/Madame <b>{escape(contrat.delegue_prenom)} {escape(contrat.delegue_nom)}</b><br/>"
        f"agissant en qualité de représentant de l'association sans but lucratif "
        f"« La Concorde » sise, 11 rue Émile Cornez à 7387 Angre/Honnelles, "
        f"ci-après dénommée <b>Propriétaire</b><br/>"
        f"D'AUTRE PART,",
        style_normal,
    ))
    elements.append(Paragraph("il est convenu ce qui suit :", style_normal))

    # --- Articles du contrat-type (modifiables sur le site) ---------------
    # Chaque titre est collé au début de son texte : il ne peut pas rester
    # seul en bas de page.
    valeurs = _valeurs_variables(reservation, contrat)
    locaux = contrat.locaux_selectionnes()
    derniers_elements = []
    for article in articles:
        corps = _texte_vers_elements(article.texte, valeurs, locaux, style_normal)
        bloc_article = [Paragraph(escape(article.titre), style_article)]
        if corps:
            bloc_article.append(KeepTogether([bloc_article.pop(), corps[0]]))
            bloc_article.extend(corps[1:])
        elements.extend(derniers_elements)
        derniers_elements = bloc_article

    # --- Signatures ------------------------------------------------------------
    # Le bloc des signatures est lié à la fin du dernier article : il ne peut
    # jamais se retrouver seul sur une page.
    style_signature = ParagraphStyle("Signature", parent=style_gauche, spaceAfter=2)
    image_sig = _image_signature(getattr(contrat, "signature", None))
    espace_signature = Spacer(1, 22 * mm)
    tableau = Table(
        [
            [Paragraph("<b>Le Délégué ASBL LA CONCORDE</b>", style_signature),
             Paragraph("<b>Le Locataire</b>", style_signature)],
            [image_sig or espace_signature, Spacer(1, 22 * mm)],
            [Paragraph(f"{escape(contrat.delegue_prenom)} {escape(contrat.delegue_nom)}", style_signature),
             Paragraph(f"{escape(reservation.prenom)} {escape(reservation.nom)}", style_signature)],
        ],
        # Largeur utile du cadre (marges et marge intérieure de 6 pt déduites)
        colWidths=[(doc.width - 12) / 2] * 2,
    )
    tableau.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 2),
    ]))
    bloc_signatures = [
        Spacer(1, 6 * mm),
        Paragraph(
            f"Fait en double exemplaire à ANGRE/HONNELLES, le {_mise_en_forme_date(date.today())}.",
            style_normal,
        ),
        Paragraph("Pour accord, précédé de la mention « Lu et approuvé »", style_normal),
        Spacer(1, 4 * mm),
        tableau,
    ]
    # Fin du dernier article (au plus ses 2 derniers éléments) + signatures.
    elements.extend(derniers_elements[:-2])
    elements.append(KeepTogether(derniers_elements[-2:] + bloc_signatures))

    doc.build(elements, onFirstPage=premiere_page, onLaterPages=pages_suivantes)
    tampon.seek(0)
    return tampon


_RE_PIED_ANNEXE = re.compile(r"ASBL\s*LA\s*CONCORDE.*la-concorde\.be", re.IGNORECASE | re.DOTALL)
_RE_NUMERO_PAGE = re.compile(r"\bpage\s*\d+(\s*(/|sur)\s*\d+)?", re.IGNORECASE)


def _page_est_vide(page):
    """Vrai pour une page d'annexe sans contenu réel : aucune image et aucun
    texte en dehors du pied de page standard de l'ASBL (évite les pages
    blanches en fin de document)."""
    try:
        ressources = page.get("/Resources")
        objets = ressources.get_object().get("/XObject") if ressources else None
        if objets:
            objets = objets.get_object()
            for nom in objets:
                if objets[nom].get_object().get("/Subtype") == "/Image":
                    return False
        texte = page.extract_text() or ""
    except Exception:
        return False
    texte = _RE_PIED_ANNEXE.sub("", " ".join(texte.split()))
    texte = _RE_NUMERO_PAGE.sub("", texte)
    return len("".join(texte.split())) < 15


def _octets_annexe(annexe):
    """Lit le contenu PDF d'une annexe enregistrée."""
    annexe.fichier.open("rb")
    try:
        return annexe.fichier.read()
    finally:
        annexe.fichier.close()


def generer_pdf_contrat(reservation, contrat, articles=None, annexes=None):
    """Génère le PDF complet du contrat (articles actifs du contrat-type +
    annexes actives) et renvoie son contenu en octets, prêt à être
    enregistré dans un fichier ou renvoyé au navigateur.

    articles / annexes : par défaut, ceux enregistrés en base (actifs
    uniquement) ; on peut les fournir directement, par exemple pour un
    aperçu ou des tests."""

    annexes_modele_origine = False
    if articles is None or annexes is None:
        from .models import AnnexeContrat, ArticleContrat

        if articles is None:
            articles = list(ArticleContrat.objects.filter(actif=True))
        if annexes is None:
            # Tant qu'aucune annexe n'a été enregistrée, on reprend celles
            # du PDF modèle d'origine.
            annexes_modele_origine = not AnnexeContrat.objects.exists()
            annexes = list(AnnexeContrat.objects.filter(actif=True))

    try:
        from .models import MiseEnPageContrat

        mise_en_page = MiseEnPageContrat.charger()
    except Exception:
        mise_en_page = None

    pages_variables = _construire_pages_variables(reservation, contrat, articles, mise_en_page)

    ecrivain = PdfWriter()
    for page in PdfReader(pages_variables).pages:
        ecrivain.add_page(page)

    # Les annexes sont ajoutées telles quelles, sauf les pages vides.
    for annexe in annexes:
        lecteur = PdfReader(io.BytesIO(_octets_annexe(annexe)))
        for page in lecteur.pages:
            if not _page_est_vide(page):
                ecrivain.add_page(page)

    if annexes_modele_origine and os.path.exists(CHEMIN_MODELE):
        lecteur_modele = PdfReader(CHEMIN_MODELE)
        for page in lecteur_modele.pages[PREMIERE_PAGE_ANNEXES:]:
            if not _page_est_vide(page):
                ecrivain.add_page(page)

    resultat = io.BytesIO()
    ecrivain.write(resultat)
    resultat.seek(0)
    return resultat.getvalue()


def nom_fichier_contrat(reservation):
    """Nom de fichier du contrat : 'Contrat de location - Nom Prénom - date
    de début.pdf', tel que demandé."""
    date_str = reservation.date_debut.strftime("%d-%m-%Y")
    return f"Contrat de location - {reservation.nom} {reservation.prenom} - {date_str}.pdf"
