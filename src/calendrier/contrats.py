"""
Génération du contrat de location de salle en PDF, à partir d'une
réservation validée et des informations complémentaires saisies dans
ContratLocationForm (délégué de l'ASBL, locaux pris en charge, montants).

Le PDF final est composé de deux parties :
1. Les pages "variables" du contrat (identité des parties, dates, locaux,
   montants, articles 1 à 12) : régénérées à chaque fois avec reportlab,
   à partir du texte du contrat-type fourni par l'ASBL.
2. Les annexes fixes (Annexe I : mobilier, Annexe II : vaisselle,
   Annexe III : conditions particulières bruit) : reprises telles quelles
   depuis le PDF modèle d'origine (calendrier/data/CONTRAT_DE_LOCATION_template.pdf),
   qui ne contient pas de champs de formulaire remplissables — seul son
   contenu fixe (les annexes) est donc réutilisé, la partie variable étant
   entièrement redessinée.

Le texte des articles 5 à 12 (clauses juridiques fixes) est repris mot
pour mot du contrat-type fourni par l'ASBL La Concorde.
"""
import io
import os
from datetime import date

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


def _construire_pages_variables(reservation, contrat):
    """Construit, avec reportlab, les pages variables du contrat (identité
    des parties, dates, locaux, montants, articles 1 à 12) et renvoie le
    résultat sous forme d'octets PDF (en mémoire, sans fichier temporaire)."""

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
        f"{reservation.prenom} {reservation.nom}<br/>"
        f"Adresse : {reservation.adresse}<br/>"
        f"Téléphone : {reservation.telephone}<br/>"
        f"Mail : {reservation.email}<br/>"
        f"Ci-après dénommé(e) <b>client</b>,<br/>"
        f"D'UNE PART,",
        style_normal,
    ))
    elements.append(Paragraph("Et", style_normal))
    elements.append(Paragraph(
        f"Monsieur/Madame <b>{contrat.delegue_prenom} {contrat.delegue_nom}</b><br/>"
        f"agissant en qualité de représentant de l'association sans but lucratif "
        f"« La Concorde » sise, 11 rue Émile Cornez à 7387 Angre/Honnelles, "
        f"ci-après dénommée <b>Propriétaire</b><br/>"
        f"D'AUTRE PART,",
        style_normal,
    ))
    elements.append(Paragraph("il est convenu ce qui suit :", style_normal))

    # --- Article 1 : locaux --------------------------------------------------
    elements.append(Paragraph("ARTICLE 1", style_article))
    elements.append(Paragraph(
        "Le propriétaire donne en location au client un ensemble de locaux "
        "ci-après définis et de mobiliers situés au 11 rue Émile Cornez à "
        "7387 Angre/Honnelles (décrits aux annexes I et II ci-jointes).<br/>"
        "Les locaux mis à disposition se composent de :",
        style_normal,
    ))
    locaux = contrat.locaux_selectionnes()
    if locaux:
        elements.append(ListFlowable(
            [ListItem(Paragraph(libelle, style_normal)) for libelle in locaux],
            bulletType="bullet",
        ))
    else:
        elements.append(Paragraph("(aucun local spécifiquement listé)", style_normal))

    # --- Article 2 : dates ----------------------------------------------------
    elements.append(Paragraph("ARTICLE 2", style_article))
    elements.append(Paragraph(
        f"Les locaux et mobiliers sont loués du <b>{_mise_en_forme_date(reservation.date_debut)}</b> "
        f"au <b>{_mise_en_forme_date(reservation.date_fin)}</b>.<br/>"
        "La prise en charge prenant cours le premier jour à 10h00*.<br/>"
        "La restitution se faisant le lendemain du dernier jour à 9h00*.",
        style_normal,
    ))

    # --- Article 3 : caution ---------------------------------------------------
    elements.append(Paragraph("ARTICLE 3", style_article))
    elements.append(Paragraph(
        "Le présent contrat est consenti et accepté moyennant le paiement du "
        "montant de la location repris à l'article 4, réglé par virement sur "
        "le numéro de compte repris en bas de page à la signature du présent "
        f"contrat. Une caution de <b>{contrat.montant_caution} €</b> sera "
        "demandée à la prise en charge des locaux et remboursable à la "
        "restitution, sous déduction des frais résultant de dommages "
        "éventuels définis à l'article 6 ci-après.<br/>"
        "En cas d'annulation moins d'un mois avant la date de location, le "
        "montant de celle-ci ne sera pas restitué.",
        style_normal,
    ))

    # --- Article 4 : coût -------------------------------------------------------
    elements.append(Paragraph("ARTICLE 4", style_article))
    elements.append(Paragraph(
        f"Le coût de location pour les locaux repris à l'article 1 est fixé à "
        f"<b>{contrat.montant_location} €</b>, TVA de 21 % et charges comprises "
        "(**), exigible en totalité à la restitution des locaux.<br/>"
        "(*) Heures et jours de prise en charge et remise des clés à confirmer "
        "quelques jours avant l'événement.<br/>"
        "(**) Par charges comprises on entend eau et électricité. Le gaz, en "
        "cas de chauffage de la salle avec consommation anormale, pourra être "
        "facturé au Locataire. L'index de consommation sera repris au présent "
        "contrat à la mise à disposition des locaux.<br/>"
        "Les prix ci-dessus sont valables pour autant que la date de location "
        "ne soit pas antérieure à la date de signature du présent contrat, "
        "auquel cas l'association se réserve le droit de réajuster ses coûts "
        "en fonction de l'index des prix.",
        style_normal,
    ))

    # --- Article 5 -----------------------------------------------------------
    elements.append(Paragraph("ARTICLE 5", style_article))
    elements.append(Paragraph(
        "Le bien est loué à destination de : Événement privé.<br/>"
        "Le Locataire ne pourra changer cette destination sans l'accord "
        "express et écrit de l'association ci-dessus, Propriétaire.<br/>"
        "Le Locataire ne pourra céder ou sous-louer les locaux et mobiliers "
        "mis à sa disposition, sous peine d'annulation immédiate du présent "
        "contrat.<br/>"
        "L'association ne peut être tenue pour responsable de négligence, "
        "vols, incendies, accidents ou autres torts ou faits nuisibles à des "
        "tiers et survenant du fait du locataire ; celui-ci, par la signature "
        "du présent contrat, s'engage à assumer toutes les responsabilités "
        "qu'elles soient civiles, morales ou pénales, de tout événement quel "
        "qu'il soit, survenant pendant la durée du présent contrat, à charge "
        "pour lui de se couvrir par une assurance ou par tout autre moyen "
        "qu'il juge nécessaire.<br/>"
        "En cas d'utilisation des pompes et en ce qui concerne les fûts de "
        "bière, le locataire devra obligatoirement s'approvisionner auprès de "
        "l'association. Il devra prévenir, au moins quinze jours au préalable, "
        "l'association pour la commande. La commande sera payable le jour de "
        "la restitution des clefs. Pour toutes les autres consommations, le "
        "Locataire est libre d'approvisionnement.",
        style_normal,
    ))

    elements.append(Paragraph("ARTICLE 5 bis", style_article))
    elements.append(Paragraph(
        "En cas d'utilisation de la salle pour des manifestations ouvertes au "
        "public, le locataire doit s'acquitter avant la date de location des "
        "droits (SACD, SABAM, Rémunération équitable). L'ASBL ne sera pas "
        "responsable des amendes éventuelles encourues en cas de non "
        "déclaration aux droits d'auteurs.",
        style_normal,
    ))

    # --- Article 6 -----------------------------------------------------------
    elements.append(Paragraph("ARTICLE 6", style_article))
    elements.append(Paragraph(
        "Le Locataire s'engage à tenir les locaux et mobiliers loués dans "
        "l'état de conservation et de propreté parfaite où ils lui ont été "
        "cédés et dont il assure s'être rendu compte à la signature du "
        "présent contrat ; si tel n'était pas le cas, tous les manquements, "
        "bris ou dégradations constatés dans le mobilier lui seront facturés "
        "au tarif défini aux annexes I et II ci-après, sans préjuger du coût "
        "des dommages constatés dans les biens, mobiliers et locaux mis à sa "
        "disposition.",
        style_normal,
    ))

    # --- Article 7 -----------------------------------------------------------
    elements.append(Paragraph("ARTICLE 7", style_article))
    elements.append(Paragraph(
        "Le Locataire s'engage à avoir procédé, à la date de restitution des "
        "locaux et mobiliers, au nettoyage complet de ceux-ci. Si tel n'était "
        "pas le cas, l'association se verrait dans l'obligation de procéder à "
        "leur remise en état, auquel cas l'intégralité de la caution "
        "resterait propriété de l'association qui délivrerait quittance et "
        "exigerait le paiement immédiat du coût de la location additionné "
        "des frais éventuels de recouvrement ainsi que de ceux dus au titre "
        "de l'article 6.",
        style_normal,
    ))

    # --- Article 8 -----------------------------------------------------------
    elements.append(Paragraph("ARTICLE 8", style_article))
    elements.append(Paragraph(
        "Le locataire ne pourra faire aux locaux et mobiliers loués aucun "
        "changement ; il lui est interdit de prendre possession de locaux "
        "autres que ceux définis à l'article 1, de déménager hors de ces "
        "locaux tout ou partie du mobilier ou vaisselle mis à sa disposition, "
        "d'afficher, de clouer, de décorer ou d'entreprendre — sans que "
        "cette liste soit limitative — tout aménagement susceptible de "
        "modifier ou détériorer tout ou partie des biens mis à sa "
        "disposition.",
        style_normal,
    ))

    # --- Article 9 -----------------------------------------------------------
    elements.append(Paragraph("ARTICLE 9", style_article))
    elements.append(Paragraph(
        "La caution, garantie de la bonne exécution des obligations du "
        "locataire, sera remboursée à ce dernier à la restitution, après "
        "qu'il aura justifié de tous ses engagements envers le délégué de "
        "l'association.",
        style_normal,
    ))

    # --- Article 10 ----------------------------------------------------------
    elements.append(Paragraph("ARTICLE 10", style_article))
    elements.append(ListFlowable(
        [
            ListItem(Paragraph(
                "Lorsque la date de location est un samedi, le locataire "
                "s'engage à avoir remis en état et procédé au nettoyage des "
                "sanitaires, ainsi que du local dénommé « Café » et de son "
                "annexe, pour le lendemain 9h00 du matin.",
                style_normal,
            )),
            ListItem(Paragraph(
                "Lorsque la date de location est un dimanche, l'association "
                "ne sera tenue de mettre à disposition du locataire les "
                "sanitaires et le local dénommé « Café », ainsi que le "
                "matériel de débit de boisson, qu'à partir de 14h30.",
                style_normal,
            )),
            ListItem(Paragraph(
                "Le présent contrat ne pouvant être conclu avec des mineurs "
                "d'âge, tout mouvement ou association de jeunes désireux de "
                "louer les locaux devra obligatoirement être représenté par "
                "un adulte, qui sera le seul habilité à signer le présent "
                "contrat et à en assumer toutes les responsabilités. Sa "
                "signature implique qu'il a pris connaissance de cette "
                "clause et qu'il s'engage à être présent le jour et pendant "
                "la durée de la location.",
                style_normal,
            )),
            ListItem(Paragraph(
                "Le locataire est tenu d'évacuer ses déchets ménagers et "
                "autres dans des sacs agréés (sacs blancs Honnelles pour "
                "déchets ménagers, sacs bleus pour PMC, papiers et cartons "
                "triés à part).",
                style_normal,
            )),
        ],
        bulletType="bullet",
    ))

    # --- Article 11 ----------------------------------------------------------
    elements.append(Paragraph("ARTICLE 11", style_article))
    elements.append(Paragraph(
        "Les annexes I et II, jointes au présent contrat, font partie "
        "intégrante de ce dernier. Le locataire déclare en avoir pris "
        "connaissance.",
        style_normal,
    ))

    # --- Article 12 ----------------------------------------------------------
    elements.append(Paragraph("ARTICLE 12", style_article))
    elements.append(Paragraph(
        "En cas de litige, seuls les tribunaux de la justice de Mons sont "
        "compétents.<br/>"
        "Le soussigné de seconde part déclare avoir pris connaissance des "
        "annexes I et II, qui font partie intégrante du présent contrat de "
        "location.<br/>"
        "Le soussigné de seconde part déclare avoir reçu un exemplaire du "
        "présent contrat de location et des annexes I et II jointes à ce "
        "dernier.",
        style_normal,
    ))

    # --- Signatures ------------------------------------------------------------
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(
        f"Fait en double exemplaire à ANGRE/HONNELLES, le {_mise_en_forme_date(date.today())}.",
        style_normal,
    ))
    elements.append(Paragraph("Pour accord, précédé de la mention « Lu et approuvé »", style_normal))
    elements.append(Spacer(1, 14 * mm))
    elements.append(Paragraph(
        f"Le Délégué ASBL LA CONCORDE : {contrat.delegue_prenom} {contrat.delegue_nom}"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        f"Le Locataire : {reservation.prenom} {reservation.nom}",
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


def generer_pdf_contrat(reservation, contrat):
    """Génère le PDF complet du contrat (pages variables régénérées +
    annexes fixes reprises du document modèle) et renvoie son contenu en
    octets, prêt à être enregistré dans un fichier ou renvoyé au navigateur."""

    pages_variables = _construire_pages_variables(reservation, contrat)

    ecrivain = PdfWriter()

    # Pages variables (régénérées).
    lecteur_variables = PdfReader(pages_variables)
    for page in lecteur_variables.pages:
        ecrivain.add_page(page)

    # Annexes fixes, reprises telles quelles du document modèle d'origine.
    if os.path.exists(CHEMIN_MODELE):
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
