"""
Données fictives pour les captures du manuel (à exécuter avec
`manage.py shell`, sur la copie de la base uniquement — voir preparer.sh).

Crée deux comptes de démonstration (mot de passe : Manuel2026!) :
- « secretariat » : super-utilisateur (Marie Dupont) ;
- « membre » : membre simple avec l'accès Théâtre (Paul Lambert).
"""
import datetime as dt
import json
import random
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.db import connection

from calendrier.models import Reservation as DemandeSalle
from newsletter.models import Abonne, Newsletter
from theatre.models import PlaceReservee, PlanSalle, Representation, Reservation, Ticket
from theatre.placement import placer_reservations

MOT_DE_PASSE = "Manuel2026!"
random.seed(4)

# --- Comptes -----------------------------------------------------------------
admin = User.objects.filter(username="secretariat").first() or User.objects.create_superuser(
    "secretariat", "secretariat@exemple.be", MOT_DE_PASSE, first_name="Marie", last_name="Dupont"
)
membre = User.objects.filter(username="membre").first() or User.objects.create_user(
    "membre", "membre@exemple.be", MOT_DE_PASSE, first_name="Paul", last_name="Lambert"
)
membre.user_permissions.add(Permission.objects.get(codename="acces_application"))

# Profil Wagtail créé d'avance : selon la version de Wagtail installée, la
# table peut contenir des colonnes obligatoires inconnues du modèle (ex :
# keyboard_shortcuts), ce qui ferait échouer sa création automatique.
with connection.cursor() as curseur:
    colonnes = {c.name for c in connection.introspection.get_table_description(curseur, "wagtailusers_userprofile")}
    valeurs = {
        "submitted_notifications": True, "approved_notifications": True, "rejected_notifications": True,
        "updated_comments_notifications": True, "preferred_language": "fr", "current_time_zone": "",
        "avatar": "", "dismissibles": json.dumps({"whats-new-in-wagtail-6.4": True, "editor-guide": True}),
        "theme": "light", "density": "default", "contrast": "system", "keyboard_shortcuts": True,
    }
    valeurs = {k: v for k, v in valeurs.items() if k in colonnes}
    for utilisateur in (admin, membre):
        curseur.execute("SELECT 1 FROM wagtailusers_userprofile WHERE user_id = %s", [utilisateur.pk])
        if not curseur.fetchone():
            champs = ["user_id", *valeurs]
            curseur.execute(
                f"INSERT INTO wagtailusers_userprofile ({', '.join(champs)}) "
                f"VALUES ({', '.join(['%s'] * len(champs))})",
                [utilisateur.pk, *valeurs.values()],
            )

# --- Théâtre : 3 représentations, réservations, plan, quelques tickets ------
if not Representation.objects.filter(nom="La Martingale").exists():
    representations = [
        Representation.objects.create(nom="La Martingale", date=d, prix_adulte=Decimal("12"), prix_enfant=Decimal("6"))
        for d in (dt.date(2026, 11, 20), dt.date(2026, 11, 21), dt.date(2026, 11, 22))
    ]
    noms = ["Dubois", "Lefèvre", "Martin", "Leroy", "Lambert", "Dupont", "Moreau", "Simon", "Laurent",
            "Michel", "Lemaire", "Renard", "Fontaine", "Henry", "Collard", "Wauters", "Jacobs", "Mertens",
            "Goossens", "Delhaye", "Bastin", "Hubert", "Piette", "Thiry", "Lecomte", "Charlier", "Gilson",
            "Denis", "Lejeune", "Noël", "Dumont", "Masson"]
    prenoms = ["Anne", "Luc", "Sophie", "Marc", "Julie", "Pierre", "Nathalie", "Olivier", "Isabelle",
               "Jean", "Christine", "Philippe", "Valérie", "Michel", "Catherine", "Éric"]
    for representation, nombre in zip(representations, (32, 18, 10)):
        for nom in noms[:nombre]:
            reservation = Reservation(
                representation=representation, nom=nom, prenom=random.choice(prenoms),
                nb_adultes=random.choice([1, 2, 2, 2, 3, 4]), nb_enfants=random.choice([0, 0, 0, 1, 2]),
                preference_rangee=random.choice(["", "", "avant", "centre", "arriere"]),
            )
            reservation.calculer_prix()
            reservation.save()
    Reservation.objects.filter(nom="Dubois", representation=representations[0]).update(
        remarque="Personne à mobilité réduite : place en bout de rangée svp."
    )
    placer_reservations(representations[0])

    plan = PlanSalle.objects.get(representation=representations[0])
    for reservation in Reservation.objects.filter(representation=representations[0]).order_by("nom")[:6]:
        places = PlaceReservee.objects.filter(plan_salle=plan, reservation=reservation).order_by("numero_place")
        for i, place in enumerate(places):
            prix = representations[0].prix_adulte if i < reservation.nb_adultes else representations[0].prix_enfant
            Ticket.objects.get_or_create(place=place, defaults={"prix_unitaire": prix})

# --- Location de salle : une demande validée, une en attente (société) ------
if not DemandeSalle.objects.filter(nom="Vandenberghe").exists():
    DemandeSalle.objects.create(
        nom="Vandenberghe", prenom="Sarah", adresse="Rue de la Station 12, 7387 Honnelles",
        email="sarah.v@exemple.be", telephone="0475 12 34 56",
        date_debut=dt.date(2026, 11, 7), date_fin=dt.date(2026, 11, 7),
        message="Anniversaire de 50 ans, environ 80 personnes.", statut="validee", traite_par=admin,
    )
    DemandeSalle.objects.create(
        type_client="societe", nom_societe="Brasserie des Honnelles SRL", numero_tva="BE 0123.456.789",
        nom="Ghislain", prenom="Marc", adresse="Chaussée Brunehault 5, 7387 Angre",
        email="contact@exemple.be", telephone="065 00 00 00",
        date_debut=dt.date(2026, 11, 28), date_fin=dt.date(2026, 11, 29),
        message="Fête du personnel.", statut="attente",
    )

# --- Newsletter --------------------------------------------------------------
for email, prenom, nom, statut, source in [
    ("anne.dubois@exemple.be", "Anne", "Dubois", "actif", "formulaire"),
    ("luc.martin@exemple.be", "Luc", "Martin", "actif", "formulaire"),
    ("sophie.leroy@exemple.be", "Sophie", "Leroy", "attente", "formulaire"),
    ("marc.simon@exemple.be", "Marc", "Simon", "actif", "admin"),
    ("julie.henry@exemple.be", "Julie", "Henry", "desinscrit", "formulaire"),
]:
    Abonne.objects.get_or_create(email=email, defaults={"prenom": prenom, "nom": nom, "statut": statut, "source": source})

if not Newsletter.objects.filter(titre="Newsletter de novembre 2026").exists():
    Newsletter.objects.create(
        titre="Newsletter de novembre 2026",
        objet="La Martingale, Ducasse d'hiver et Marché de Noël",
        preheader="Tout le programme de fin d'année à La Concorde",
        contenu=[
            ("titre", "Au programme ce mois-ci"),
            ("texte", "<p>Le Blé qui Lève remonte sur les planches avec <b>La Martingale</b> "
                      "les 20, 21 et 22 novembre. Réservez vite vos places !</p>"),
            ("actualites", {"nombre": 3}),
            ("separateur", None),
            ("texte", "<p>À très bientôt à la salle La Concorde.</p>"),
        ],
    )

# --- Actualité composée avec l'éditeur par blocs du site -------------------
from news.models import NewsIndexPage as _IndexActus, NewsPage as _Actu  # noqa: E402
from wagtail.images import get_image_model as _modele_image  # noqa: E402

TITRE_ACTU_BLOCS = "Le Blé qui Lève prépare La Martingale"
if not _Actu.objects.filter(title=TITRE_ACTU_BLOCS).exists():
    _photo = _modele_image().objects.filter(collection__name__iexact="La bonne adresse").first() or _modele_image().objects.first()
    _actu = _Actu(
        title=TITRE_ACTU_BLOCS, slug="ble-qui-leve-prepare-la-martingale", date=dt.date(2026, 10, 5),
        author="Marie Dupont", intro="Les répétitions battent leur plein avant les représentations de novembre.",
        cree_par=User.objects.get(username="secretariat"),
    )
    _actu.body = [
        ("paragraph", "<p>Depuis la rentrée, la troupe du <b>Blé qui Lève</b> se retrouve deux soirs par "
                      "semaine à la salle La Concorde pour préparer <i>La Martingale</i>.</p>"),
        ("image_positionnee", {"image": _photo, "position": "gauche", "legende": "Répétition du mardi soir"}),
        ("paragraph", "<p>Décors, costumes, éclairages : chacun met la main à la pâte. Les comédiens "
                      "peaufinent leurs répliques sous l'œil attentif de la metteuse en scène, et les "
                      "bénévoles montent le décor du salon bourgeois où se déroule la pièce.</p>"
                      "<p>Rendez-vous les 20, 21 et 22 novembre pour découvrir le résultat. Les "
                      "réservations sont ouvertes dès maintenant.</p>"),
        ("quote", {"text": "On a hâte de retrouver notre public !", "attribution": "La troupe"}),
    ]
    _IndexActus.objects.first().add_child(instance=_actu)
    _actu.save_revision().publish()

# --- Statistiques de fréquentation : un an de chiffres fictifs ---------------
from django.utils import timezone

from statistiques.models import Jour, PageJour, ProvenanceJour

PAGES_STATS = [("/", 1.0), ("/news/", .45), ("/calendrier/", .4), ("/medias/", .3), ("/contact/", .18),
               ("/info/", .12), ("/news/marche-de-noel-2026/", .2), ("/newsletter/", .06)]
PROVENANCES_STATS = [("Facebook", .22), ("Google", .18), ("Gmail", .05), ("honnelles.be", .02), ("Instagram", .03)]
Jour.objects.all().delete()
PageJour.objects.all().delete()
ProvenanceJour.objects.all().delete()
aujourdhui = timezone.localdate()
jours, pages_jour, provenances_jour = [], [], []
for ecart in range(365):
    date = aujourdhui - dt.timedelta(days=ecart)
    # Plus de monde le week-end et à l'approche des fêtes de fin d'année
    visiteurs = int((40 + 25 * (date.weekday() >= 4) + 30 * (date.month in (11, 12))) * random.uniform(.7, 1.3))
    vues = int(visiteurs * random.uniform(2.1, 2.9))
    jours.append(Jour(date=date, vues=vues, visiteurs=visiteurs, vues_mobiles=int(vues * random.uniform(.55, .7))))
    pages_jour += [PageJour(date=date, chemin=c, vues=max(1, int(vues * p / 2.7))) for c, p in PAGES_STATS]
    provenances_jour += [ProvenanceJour(date=date, source=s, vues=max(1, int(visiteurs * p)))
                         for s, p in PROVENANCES_STATS]
Jour.objects.bulk_create(jours)
PageJour.objects.bulk_create(pages_jour)
ProvenanceJour.objects.bulk_create(provenances_jour)

# --- Planning des membres : événements, créneaux, sondage, discussions -------
from planning import services as planning_services  # noqa: E402
from planning.models import (  # noqa: E402
    Canal as PlCanal, Creneau as PlCreneau, Disponibilite as PlDispo, Evenement as PlEvenement,
    Inscription as PlInscription, Invitation as PlInvitation, Message as PlMessage,
    Notification as PlNotification, Sondage as PlSondage, Vote as PlVote,
)

def _membre(identifiant, prenom, nom):
    return User.objects.filter(username=identifiant).first() or User.objects.create_user(
        identifiant, f"{identifiant}@exemple.be", MOT_DE_PASSE, first_name=prenom, last_name=nom)

benevoles = [_membre("sophie", "Sophie", "Leroy"), _membre("marc", "Marc", "Petit"),
             _membre("julie", "Julie", "Hennaut"), _membre("luc", "Luc", "Duvivier")]
sophie, marc, julie, luc = benevoles
# Les vrais comptes de la base copiée n'apparaissent pas dans les listes de
# membres des captures (copie de travail uniquement)
User.objects.exclude(pk__in=[admin.pk, membre.pk] + [b.pk for b in benevoles]).update(is_active=False)

def _a(jour, heure, minute=0):
    return timezone.make_aware(dt.datetime.combine(jour, dt.time(heure, minute)))

for modele in (PlNotification, PlVote, PlSondage, PlMessage, PlEvenement):
    modele.objects.all().delete()
PlDispo.objects.all().delete()

ducasse = PlEvenement.objects.create(
    type="activite", titre="Ducasse d'hiver — souper raclette", lieu="Salle La Concorde", createur=admin,
    description="Montage l'après-midi, service du souper le soir, rangement en fin de soirée.",
    debut=_a(dt.date(2026, 11, 14), 14), fin=_a(dt.date(2026, 11, 14), 23))
for heure, fin, poste, besoin, inscrits in [
    (14, 17, "Montage de la salle", 4, [marc, luc, membre]), (18, 20, "Bar", 2, [sophie, julie]),
    (20, 22, "Bar", 2, [sophie]), (18, 21, "Service à table", 3, []), (21, 23, "Vaisselle et rangement", 3, [luc]),
]:
    creneau = PlCreneau.objects.create(evenement=ducasse, libelle=poste, besoin=besoin,
                                       debut=_a(dt.date(2026, 11, 14), heure), fin=_a(dt.date(2026, 11, 14), fin))
    for m in inscrits:
        PlInscription.objects.create(creneau=creneau, membre=m)

comite = PlEvenement.objects.create(
    type="reunion", titre="Réunion du comité", lieu="Petite salle", createur=admin, reserve_aux_invites=False,
    description="Ordre du jour : bilan de la ducasse, préparation du marché de Noël.",
    debut=_a(dt.date(2026, 11, 4), 20), fin=_a(dt.date(2026, 11, 4), 22))
for occurrence in [comite] + planning_services.repeter(comite, "mois", dt.date(2027, 3, 31)):
    for m, statut in [(membre, "accepte"), (sophie, "accepte"), (marc, "refuse"), (julie, "attente")]:
        PlInvitation.objects.create(evenement=occurrence, membre=m, statut=statut)

menage = PlEvenement.objects.create(type="tache", titre="Ménage de la salle", createur=admin,
                                    debut=_a(dt.date(2026, 10, 26), 9), fin=_a(dt.date(2026, 10, 26), 11))
planning_services.decouper(menage, 120, 2)
for occurrence in planning_services.repeter(menage, "hebdo", dt.date(2026, 12, 21)):
    planning_services.copier_creneaux(menage, [occurrence])
PlInscription.objects.create(creneau=menage.creneaux.first(), membre=julie)

marche = PlEvenement.objects.create(
    type="activite", titre="Marché de Noël — stands et accueil", lieu="Salle et parking", createur=admin,
    debut=_a(dt.date(2026, 12, 5), 16), fin=_a(dt.date(2026, 12, 5), 22))
planning_services.decouper(marche, 120, 3, "Accueil des visiteurs")
planning_services.decouper(marche, 180, 2, "Bar à vin chaud")

PlDispo.objects.bulk_create([
    PlDispo(membre=julie, date=dt.date(2026, 11, 14), heure_debut=dt.time(17)),
    PlDispo(membre=marc, date=dt.date(2026, 11, 14), note="Après le montage"),
    PlDispo(membre=membre, date=dt.date(2026, 12, 5)),
])

sondage_bilan = PlSondage.objects.create(type="date", titre="Réunion bilan de la ducasse", createur=admin,
                                         description="Une heure pour faire le point à chaud.")
options = [sondage_bilan.options.create(debut=_a(j, 20), fin=_a(j, 21), ordre=i)
           for i, j in enumerate([dt.date(2026, 11, 17), dt.date(2026, 11, 18), dt.date(2026, 11, 19)])]
for m, reponses in [(sophie, ["oui", "si_besoin", "non"]), (marc, ["oui", "oui", "non"]),
                    (julie, ["non", "oui", "oui"]), (luc, ["oui", "non", "si_besoin"])]:
    for option, reponse in zip(options, reponses):
        PlVote.objects.create(option=option, membre=m, reponse=reponse)
sondage_tshirts = PlSondage.objects.create(type="decision", titre="Couleur des t-shirts des bénévoles", createur=admin)
for libelle, votants in [("Bordeaux", [sophie, marc, luc]), ("Noir", [julie]), ("Doré", [])]:
    option = sondage_tshirts.options.create(libelle=libelle)
    for m in votants:
        PlVote.objects.create(option=option, membre=m)

general = PlCanal.objects.get_or_create(nom="Général", evenement=None)[0]
for auteur, texte in [
    (sophie, "Bonjour à tous ! Qui a la clé du local de rangement cette semaine ?"),
    (marc, "C'est moi, je la dépose au bar vendredi soir."),
    (admin, "Merci Marc. N'oubliez pas de vous inscrire pour la ducasse : il manque encore du monde au service à table."),
    (julie, "@membre tu pourrais faire le service avec moi samedi ?"),
]:
    planning_services.publier(general, auteur, texte)
fil = planning_services.canal_de(ducasse)
for auteur, texte in [(luc, "J'apporte les rallonges électriques pour les appareils à raclette."),
                      (sophie, "Super ! Pour le bar, on prévoit combien de fûts ? @secretariat")]:
    planning_services.publier(fil, auteur, texte)

# --- Invitations de nouveaux membres -----------------------------------------
from comptes.models import InvitationMembre, empreinte  # noqa: E402

InvitationMembre.objects.all().delete()
InvitationMembre.objects.create(
    email="lea.vandenberg@exemple.be", prenom="Léa", nom="Van den Berg", invite_par=admin,
    message="Bienvenue dans l'équipe ! Tu trouveras le planning du bar dans le menu Réservations.",
    jeton_hache=empreinte("invitation-demo-manuel"), envoyee_le=timezone.now(),
    expire_le=timezone.now() + dt.timedelta(days=14))
InvitationMembre.objects.create(
    email="luc@exemple.be", prenom="Luc", nom="Duvivier", invite_par=admin, membre=luc,
    jeton_hache=empreinte("invitation-demo-acceptee"), envoyee_le=timezone.now() - dt.timedelta(days=9),
    acceptee_le=timezone.now() - dt.timedelta(days=8), expire_le=timezone.now() + dt.timedelta(days=5))

# --- Identifiants utiles aux captures (lus par captures.py) -----------------
from pathlib import Path  # noqa: E402

from calendrier.models import Activite  # noqa: E402
from media_gallery.models import GalleryAlbum, GalleryVideo  # noqa: E402
from navigation.models import MainMenu  # noqa: E402
from news.models import NewsPage  # noqa: E402

album_video = GalleryVideo.objects.order_by("page_id").values_list("page_id", flat=True).first()
albums_photos = GalleryAlbum.objects.live().filter(gallery_images__isnull=False).distinct()
album_photos = albums_photos.filter(videos__isnull=False).first() or albums_photos.first()
activite_privee = Activite.objects.filter(visibilite=Activite.VISIBILITE_PRIVEE).first()
ids = {
    "demande_validee": DemandeSalle.objects.get(nom="Vandenberghe").pk,
    "demande_attente": DemandeSalle.objects.get(nom="Ghislain").pk,
    "representation": Representation.objects.filter(nom="La Martingale").order_by("date")[0].pk,
    "representation_2": Representation.objects.filter(nom="La Martingale").order_by("date")[1].pk,
    "newsletter": Newsletter.objects.get(titre="Newsletter de novembre 2026").pk,
    "membre": membre.pk,
    "album_photos": album_photos.pk if album_photos else None,
    "album_photos_url": album_photos.url if album_photos else None,
    "album_video": album_video,
    "actualite": NewsPage.objects.live().order_by("-date").first().pk,
    "actualite_url": NewsPage.objects.live().order_by("-date").first().url,
    "accueil": NewsPage.objects.first().get_parent().get_parent().pk,
    "activite_privee": activite_privee.pk if activite_privee else None,
    "menu": MainMenu.objects.first().pk,
    "actualite_blocs": NewsPage.objects.get(title=TITRE_ACTU_BLOCS).pk,
    "actualite_blocs_url": NewsPage.objects.get(title=TITRE_ACTU_BLOCS).url,
    "planning_ducasse": ducasse.pk,
    "planning_comite": comite.pk,
    "planning_sondage": sondage_bilan.pk,
    "planning_sondage_decision": sondage_tshirts.pk,
    "planning_canal": general.pk,
}
fichier = Path(connection.settings_dict["NAME"]).parent / "ids.json"
fichier.write_text(json.dumps(ids, indent=2, ensure_ascii=False))
print("Données de démonstration prêtes :", fichier)
