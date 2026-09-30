"""
Remplit le contrat-type avec le texte d'origine du contrat de location de
La Concorde (articles 1 à 12) et découpe les annexes du PDF modèle en deux
fichiers remplaçables : annexes I et II (mobilier, vaisselle), annexe III
(conditions particulières).
"""
import io
import os

from django.db import migrations

ARTICLES = [
    ("ARTICLE 1",
     "Le propriétaire donne en location au client un ensemble de locaux "
     "ci-après définis et de mobiliers situés au 11 rue Émile Cornez à "
     "7387 Angre/Honnelles (décrits aux annexes I et II ci-jointes).\n"
     "Les locaux mis à disposition se composent de :\n"
     "{locaux}"),
    ("ARTICLE 2",
     "Les locaux et mobiliers sont loués du **{date_debut}** au **{date_fin}**.\n"
     "La prise en charge prenant cours le premier jour à 10h00*.\n"
     "La restitution se faisant le lendemain du dernier jour à 9h00*."),
    ("ARTICLE 3",
     "Le présent contrat est consenti et accepté moyennant le paiement du "
     "montant de la location repris à l'article 4, réglé par virement sur "
     "le numéro de compte repris en bas de page à la signature du présent "
     "contrat. Une caution de **{montant_caution} €** sera demandée à la "
     "prise en charge des locaux et remboursable à la restitution, sous "
     "déduction des frais résultant de dommages éventuels définis à "
     "l'article 6 ci-après.\n"
     "En cas d'annulation moins d'un mois avant la date de location, le "
     "montant de celle-ci ne sera pas restitué."),
    ("ARTICLE 4",
     "Le coût de location pour les locaux repris à l'article 1 est fixé à "
     "**{montant_location} €**, TVA de 21 % et charges comprises (**), "
     "exigible en totalité à la restitution des locaux.\n"
     "(*) Heures et jours de prise en charge et remise des clés à confirmer "
     "quelques jours avant l'événement.\n"
     "(**) Par charges comprises on entend eau et électricité. Le gaz, en "
     "cas de chauffage de la salle avec consommation anormale, pourra être "
     "facturé au Locataire. L'index de consommation sera repris au présent "
     "contrat à la mise à disposition des locaux.\n"
     "Les prix ci-dessus sont valables pour autant que la date de location "
     "ne soit pas antérieure à la date de signature du présent contrat, "
     "auquel cas l'association se réserve le droit de réajuster ses coûts "
     "en fonction de l'index des prix."),
    ("ARTICLE 5",
     "Le bien est loué à destination de : Événement privé.\n"
     "Le Locataire ne pourra changer cette destination sans l'accord "
     "express et écrit de l'association ci-dessus, Propriétaire.\n"
     "Le Locataire ne pourra céder ou sous-louer les locaux et mobiliers "
     "mis à sa disposition, sous peine d'annulation immédiate du présent "
     "contrat.\n"
     "L'association ne peut être tenue pour responsable de négligence, "
     "vols, incendies, accidents ou autres torts ou faits nuisibles à des "
     "tiers et survenant du fait du locataire ; celui-ci, par la signature "
     "du présent contrat, s'engage à assumer toutes les responsabilités "
     "qu'elles soient civiles, morales ou pénales, de tout événement quel "
     "qu'il soit, survenant pendant la durée du présent contrat, à charge "
     "pour lui de se couvrir par une assurance ou par tout autre moyen "
     "qu'il juge nécessaire.\n"
     "En cas d'utilisation des pompes et en ce qui concerne les fûts de "
     "bière, le locataire devra obligatoirement s'approvisionner auprès de "
     "l'association. Il devra prévenir, au moins quinze jours au préalable, "
     "l'association pour la commande. La commande sera payable le jour de "
     "la restitution des clefs. Pour toutes les autres consommations, le "
     "Locataire est libre d'approvisionnement."),
    ("ARTICLE 5 bis",
     "En cas d'utilisation de la salle pour des manifestations ouvertes au "
     "public, le locataire doit s'acquitter avant la date de location des "
     "droits (SACD, SABAM, Rémunération équitable). L'ASBL ne sera pas "
     "responsable des amendes éventuelles encourues en cas de non "
     "déclaration aux droits d'auteurs."),
    ("ARTICLE 6",
     "Le Locataire s'engage à tenir les locaux et mobiliers loués dans "
     "l'état de conservation et de propreté parfaite où ils lui ont été "
     "cédés et dont il assure s'être rendu compte à la signature du "
     "présent contrat ; si tel n'était pas le cas, tous les manquements, "
     "bris ou dégradations constatés dans le mobilier lui seront facturés "
     "au tarif défini aux annexes I et II ci-après, sans préjuger du coût "
     "des dommages constatés dans les biens, mobiliers et locaux mis à sa "
     "disposition."),
    ("ARTICLE 7",
     "Le Locataire s'engage à avoir procédé, à la date de restitution des "
     "locaux et mobiliers, au nettoyage complet de ceux-ci. Si tel n'était "
     "pas le cas, l'association se verrait dans l'obligation de procéder à "
     "leur remise en état, auquel cas l'intégralité de la caution "
     "resterait propriété de l'association qui délivrerait quittance et "
     "exigerait le paiement immédiat du coût de la location additionné "
     "des frais éventuels de recouvrement ainsi que de ceux dus au titre "
     "de l'article 6."),
    ("ARTICLE 8",
     "Le locataire ne pourra faire aux locaux et mobiliers loués aucun "
     "changement ; il lui est interdit de prendre possession de locaux "
     "autres que ceux définis à l'article 1, de déménager hors de ces "
     "locaux tout ou partie du mobilier ou vaisselle mis à sa disposition, "
     "d'afficher, de clouer, de décorer ou d'entreprendre — sans que "
     "cette liste soit limitative — tout aménagement susceptible de "
     "modifier ou détériorer tout ou partie des biens mis à sa "
     "disposition."),
    ("ARTICLE 9",
     "La caution, garantie de la bonne exécution des obligations du "
     "locataire, sera remboursée à ce dernier à la restitution, après "
     "qu'il aura justifié de tous ses engagements envers le délégué de "
     "l'association."),
    ("ARTICLE 10",
     "- Lorsque la date de location est un samedi, le locataire s'engage à "
     "avoir remis en état et procédé au nettoyage des sanitaires, ainsi "
     "que du local dénommé « Café » et de son annexe, pour le lendemain "
     "9h00 du matin.\n"
     "- Lorsque la date de location est un dimanche, l'association ne sera "
     "tenue de mettre à disposition du locataire les sanitaires et le "
     "local dénommé « Café », ainsi que le matériel de débit de boisson, "
     "qu'à partir de 14h30.\n"
     "- Le présent contrat ne pouvant être conclu avec des mineurs d'âge, "
     "tout mouvement ou association de jeunes désireux de louer les locaux "
     "devra obligatoirement être représenté par un adulte, qui sera le "
     "seul habilité à signer le présent contrat et à en assumer toutes les "
     "responsabilités. Sa signature implique qu'il a pris connaissance de "
     "cette clause et qu'il s'engage à être présent le jour et pendant la "
     "durée de la location.\n"
     "- Le locataire est tenu d'évacuer ses déchets ménagers et autres dans "
     "des sacs agréés (sacs blancs Honnelles pour déchets ménagers, sacs "
     "bleus pour PMC, papiers et cartons triés à part)."),
    ("ARTICLE 11",
     "Les annexes I et II, jointes au présent contrat, font partie "
     "intégrante de ce dernier. Le locataire déclare en avoir pris "
     "connaissance."),
    ("ARTICLE 12",
     "En cas de litige, seuls les tribunaux de la justice de Mons sont "
     "compétents.\n"
     "Le soussigné de seconde part déclare avoir pris connaissance des "
     "annexes I et II, qui font partie intégrante du présent contrat de "
     "location.\n"
     "Le soussigné de seconde part déclare avoir reçu un exemplaire du "
     "présent contrat de location et des annexes I et II jointes à ce "
     "dernier."),
]

# Pages (0-indexées) du PDF modèle : fin exclue.
ANNEXES = [
    ("Annexes I et II — Mobilier et vaisselle", "annexes_I_II_mobilier_vaisselle.pdf", 5, 9),
    ("Annexe III — Conditions particulières", "annexe_III_conditions_particulieres.pdf", 9, 11),
]

CHEMIN_MODELE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "CONTRAT_DE_LOCATION_template.pdf",
)


def creer_contrat_type(apps, schema_editor):
    ArticleContrat = apps.get_model("calendrier", "ArticleContrat")
    AnnexeContrat = apps.get_model("calendrier", "AnnexeContrat")

    if not ArticleContrat.objects.exists():
        for position, (titre, texte) in enumerate(ARTICLES, start=1):
            ArticleContrat.objects.create(ordre=position * 10, titre=titre, texte=texte)

    if AnnexeContrat.objects.exists() or not os.path.exists(CHEMIN_MODELE):
        return

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from pypdf import PdfReader, PdfWriter

    modele = PdfReader(CHEMIN_MODELE)
    for position, (titre, nom_fichier, debut, fin) in enumerate(ANNEXES, start=1):
        ecrivain = PdfWriter()
        for page in modele.pages[debut:min(fin, len(modele.pages))]:
            ecrivain.add_page(page)
        tampon = io.BytesIO()
        ecrivain.write(tampon)
        chemin = default_storage.save(f"annexes_contrat/{nom_fichier}", ContentFile(tampon.getvalue()))
        AnnexeContrat.objects.create(ordre=position * 10, titre=titre, fichier=chemin)


def rien(apps, schema_editor):
    """Retour arrière : les tables sont supprimées par la migration 0003."""


class Migration(migrations.Migration):

    dependencies = [
        ("calendrier", "0003_articlecontrat_annexecontrat"),
    ]

    operations = [
        migrations.RunPython(creer_contrat_type, rien),
    ]
