"""
Contenu de la page « Politique de confidentialité » de La Concorde asbl.

Rédigé d'après les traitements de données réellement présents sur le site
(formulaire de contact, réservations de salle et contrats, suivi des
paiements, billetterie du théâtre, comptes des membres, cookies).
Utilisé par la commande : python manage.py creer_page_confidentialite

Chaque élément est (type de bloc, contenu) pour le StreamField de InfoPage :
"heading" (texte), "paragraph" (HTML), "callout" (titre, HTML).
"""

DATE_MISE_A_JOUR = "4 octobre 2026"

CONTENU = [
    ("callout", ("En résumé",
        "<p>La Concorde asbl ne collecte que les données nécessaires pour répondre "
        "à vos messages, gérer les locations de la salle et les réservations de "
        "spectacles. Elles ne sont jamais vendues ni utilisées à des fins publicitaires. "
        "Le site n'utilise aucun outil de mesure d'audience ni de publicité.</p>")),

    ("heading", "1. Qui est responsable de vos données ?"),
    ("paragraph",
        "<p>Le responsable du traitement est :</p>"
        "<p><b>La Concorde asbl</b><br/>Rue Émile Cornez 11<br/>7387 Angre (Honnelles), Belgique<br/>"
        "Numéro d'entreprise : 0412.730.545<br/>"
        "E-mail : <a href=\"mailto:infos@la-concorde.be\">infos@la-concorde.be</a><br/>"
        "Téléphone : 065 75 01 75</p>"
        "<p>Pour toute question relative à vos données personnelles, vous pouvez nous "
        "écrire à l'adresse ci-dessus.</p>"),

    ("heading", "2. Quelles données collectons-nous, et pourquoi ?"),
    ("paragraph",
        "<p><b>Formulaire de contact</b><br/>"
        "Données : nom, prénom, adresse e-mail, objet et contenu de votre message.<br/>"
        "Finalité : répondre à votre demande.<br/>"
        "Base légale : notre intérêt légitime à répondre aux personnes qui nous contactent, "
        "ou les mesures préalables à un contrat prises à votre demande.<br/>"
        "Durée de conservation : 2 ans au maximum après notre dernier échange.</p>"),
    ("paragraph",
        "<p><b>Demandes de réservation et location de la salle</b><br/>"
        "Données : nom, prénom, adresse, téléphone, adresse e-mail, dates souhaitées et "
        "précisions de votre demande ; en cas de location, le contrat de location "
        "(locaux, montants de la location et de la caution) ainsi que le suivi des paiements "
        "et du remboursement de la caution (dates et références des extraits bancaires).<br/>"
        "Finalités : traiter votre demande, établir et exécuter le contrat de location, "
        "tenir notre comptabilité.<br/>"
        "Base légale : l'exécution du contrat ou des mesures préalables à sa conclusion ; "
        "le respect de nos obligations légales comptables pour les pièces justificatives.<br/>"
        "Durée de conservation : 1 an pour une demande qui n'aboutit pas ; pour une location, "
        "le contrat et les pièces de paiement sont conservés pendant la durée imposée par "
        "la législation comptable (actuellement jusqu'à 10 ans).</p>"),
    ("paragraph",
        "<p><b>Réservations pour les spectacles</b><br/>"
        "Données : nom, prénom, nombre de places (adultes et enfants), préférences de "
        "placement et remarques éventuelles.<br/>"
        "Finalités : réserver vos places, organiser le placement en salle et la billetterie.<br/>"
        "Base légale : l'exécution de votre réservation.<br/>"
        "Durée de conservation : jusqu'à la fin de la saison théâtrale concernée ; les "
        "données liées aux ventes sont conservées le temps requis par nos obligations comptables.</p>"),
    ("paragraph",
        "<p><b>Comptes des membres et administrateurs du site</b><br/>"
        "Données : nom, prénom, identifiant, adresse e-mail et mot de passe (enregistré "
        "uniquement sous forme chiffrée).<br/>"
        "Finalité : permettre aux bénévoles habilités de gérer le site, le calendrier et les "
        "réservations.<br/>"
        "Base légale : notre intérêt légitime à organiser les activités de l'association.<br/>"
        "Durée de conservation : tant que la personne exerce une fonction au sein de "
        "l'association, puis suppression du compte.</p>"),
    ("paragraph",
        "<p><b>Navigation sur le site</b><br/>"
        "Notre hébergeur conserve des journaux techniques (adresse IP, pages consultées, date "
        "et heure) pour assurer la sécurité et le bon fonctionnement du serveur, pendant une "
        "durée limitée. Les mots recherchés avec la recherche du site sont enregistrés sans "
        "aucun lien avec votre identité, pour améliorer les résultats.</p>"),

    ("heading", "3. Cookies"),
    ("paragraph",
        "<p>Le site dépose uniquement les cookies <b>strictement nécessaires</b> à son "
        "fonctionnement, qui ne demandent pas votre consentement :</p>"
        "<ul>"
        "<li><b>sessionid</b> : maintient la connexion des membres et administrateurs "
        "(2 semaines au maximum) ;</li>"
        "<li><b>csrftoken</b> : protège les formulaires contre les envois frauduleux (1 an) ;</li>"
        "<li><b>concorde_cookies</b> : mémorise votre choix concernant les contenus externes "
        "(6 mois).</li>"
        "</ul>"
        "<p><b>Contenus externes.</b> Certaines pages intègrent des cartes Google Maps ou des "
        "vidéos (YouTube, Vimeo, Facebook…). Ces services peuvent déposer leurs propres cookies "
        "et collecter des données sur votre navigation, sous leur propre responsabilité. "
        "Ils ne sont chargés qu'avec votre accord, donné via le bandeau affiché lors de votre "
        "première visite ou le bouton « Afficher ce contenu ».</p>"
        "<p>Vous pouvez modifier votre choix à tout moment grâce au lien "
        "<b>« Gérer les cookies »</b> en bas de chaque page.</p>"),

    ("heading", "4. Qui a accès à vos données ?"),
    ("paragraph",
        "<p>Vos données sont accessibles uniquement aux membres du conseil d'administration "
        "et aux bénévoles de l'association habilités à traiter votre demande. Elles ne sont "
        "jamais vendues, louées ni cédées.</p>"
        "<p>Elles peuvent être communiquées :</p>"
        "<ul>"
        "<li>à notre hébergeur, <b>o2switch</b> (Clermont-Ferrand, France), qui héberge le site "
        "et les données pour notre compte, au sein de l'Union européenne ;</li>"
        "<li>à notre banque, pour les paiements et remboursements liés à une location ;</li>"
        "<li>aux autorités, uniquement lorsque la loi nous y oblige.</li>"
        "</ul>"
        "<p>Si vous acceptez les contenus externes, Google (Google Maps) et les plateformes "
        "vidéo reçoivent des données de navigation et peuvent les transférer hors de l'Union "
        "européenne, notamment aux États-Unis, dans le cadre de leurs propres garanties "
        "(Data Privacy Framework UE–États-Unis). Aucun autre transfert hors de l'Union "
        "européenne n'a lieu.</p>"),

    ("heading", "5. Comment protégeons-nous vos données ?"),
    ("paragraph",
        "<p>Le site est accessible en connexion sécurisée (HTTPS). Les espaces de gestion sont "
        "réservés aux personnes habilitées, les mots de passe sont enregistrés sous forme "
        "chiffrée, les contrats de location ne sont jamais accessibles publiquement et les "
        "données sont sauvegardées régulièrement.</p>"),

    ("heading", "6. Quels sont vos droits ?"),
    ("paragraph",
        "<p>Conformément au Règlement général sur la protection des données (RGPD), vous "
        "pouvez à tout moment :</p>"
        "<ul>"
        "<li>accéder à vos données et en obtenir une copie ;</li>"
        "<li>les faire rectifier si elles sont inexactes ou incomplètes ;</li>"
        "<li>demander leur effacement, sauf si la loi nous impose de les conserver ;</li>"
        "<li>demander la limitation de leur traitement ou vous y opposer ;</li>"
        "<li>recevoir les données que vous nous avez fournies dans un format courant "
        "(portabilité) ;</li>"
        "<li>retirer votre consentement aux contenus externes, via « Gérer les cookies ».</li>"
        "</ul>"
        "<p>Pour exercer vos droits, écrivez-nous à "
        "<a href=\"mailto:infos@la-concorde.be\">infos@la-concorde.be</a> ou par courrier à "
        "l'adresse de l'association. Nous vous répondrons dans un délai d'un mois. Nous "
        "pourrons vous demander de justifier de votre identité si nous avons un doute "
        "raisonnable à ce sujet.</p>"),

    ("heading", "7. Introduire une réclamation"),
    ("paragraph",
        "<p>Si vous estimez que vos droits ne sont pas respectés, vous pouvez introduire une "
        "réclamation auprès de l'<b>Autorité de protection des données</b> :<br/>"
        "Rue de la Presse 35, 1000 Bruxelles<br/>"
        "E-mail : <a href=\"mailto:contact@apd-gba.be\">contact@apd-gba.be</a><br/>"
        "Site : <a href=\"https://www.autoriteprotectiondonnees.be\">www.autoriteprotectiondonnees.be</a></p>"
        "<p>N'hésitez pas à nous contacter d'abord : nous ferons tout pour trouver une solution.</p>"),

    ("heading", "8. Modifications de cette politique"),
    ("paragraph",
        "<p>Cette politique peut être mise à jour, notamment en cas d'évolution du site ou de "
        "la réglementation. La date de la dernière mise à jour figure ci-dessous.</p>"
        f"<p><i>Dernière mise à jour : {DATE_MISE_A_JOUR}.</i></p>"),
]
