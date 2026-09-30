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
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
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


def _construire_pages_variables(reservation, contrat, articles):
    """Construit, avec reportlab, les pages variables du contrat (identité
    des parties, puis chaque article actif du contrat-type, signatures) et
    renvoie le résultat en mémoire, sans fichier temporaire."""

    tampon = io.BytesIO()
    doc = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        title="Contrat de location — La Concorde asbl",
    )

    styles = getSampleStyleSheet()
    style_titre = ParagraphStyle(
        "TitreContrat", parent=styles["Title"], fontSize=16, spaceAfter=14,
    )
    style_article = ParagraphStyle(
        "Article", parent=styles["Heading2"], fontSize=11, spaceBefore=14, spaceAfter=6,
    )
    style_normal = ParagraphStyle(
        "CorpsContrat", parent=styles["Normal"], fontSize=9.5, leading=13.5, spaceAfter=8,
        alignment=4,  # justifié
    )
    style_petit = ParagraphStyle(
        "PetitContrat", parent=styles["Normal"], fontSize=8, leading=11, textColor="#555555",
    )

    elements = []

    # --- En-tête -----------------------------------------------------------
    elements.append(Paragraph("La Concorde asbl", style_titre))
    elements.append(Paragraph(
        "Rue Émile Cornez 11 — 7387 Angre/Honnelles — BE0412.730.545", style_petit,
    ))
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
        style_normal,
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
    valeurs = _valeurs_variables(reservation, contrat)
    locaux = contrat.locaux_selectionnes()
    for article in articles:
        elements.append(Paragraph(escape(article.titre), style_article))
        elements.extend(_texte_vers_elements(article.texte, valeurs, locaux, style_normal))

    # --- Signatures ------------------------------------------------------------
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(
        f"Fait en double exemplaire à ANGRE/HONNELLES, le {_mise_en_forme_date(date.today())}.",
        style_normal,
    ))
    elements.append(Paragraph("Pour accord, précédé de la mention « Lu et approuvé »", style_normal))
    elements.append(Spacer(1, 14 * mm))
    elements.append(Paragraph(
        f"Le Délégué ASBL LA CONCORDE : {escape(contrat.delegue_prenom)} {escape(contrat.delegue_nom)}"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        f"Le Locataire : {escape(reservation.prenom)} {escape(reservation.nom)}",
        style_normal,
    ))

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "ASBL LA CONCORDE – Contrat de Location (conditions 2019) — "
        "Compte de la poste : BE 73 0000 9818 9460 - BIC : BPOTBEB - "
        "TVA BE 0412.730.545 — Tél : 065/75 01 75 - "
        "Adresse mail : infos@la-concorde.be - www.la-concorde.be",
        style_petit,
    ))

    doc.build(elements)
    tampon.seek(0)
    return tampon


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

    pages_variables = _construire_pages_variables(reservation, contrat, articles)

    ecrivain = PdfWriter()
    for page in PdfReader(pages_variables).pages:
        ecrivain.add_page(page)

    for annexe in annexes:
        lecteur = PdfReader(io.BytesIO(_octets_annexe(annexe)))
        for page in lecteur.pages:
            ecrivain.add_page(page)

    if annexes_modele_origine and os.path.exists(CHEMIN_MODELE):
        lecteur_modele = PdfReader(CHEMIN_MODELE)
        for page in lecteur_modele.pages[PREMIERE_PAGE_ANNEXES:]:
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
