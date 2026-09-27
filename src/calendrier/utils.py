"""
Fonctions utilitaires pour construire la grille du calendrier mensuel,
avec application des règles de visibilité selon le profil de l'utilisateur :

- Visiteur anonyme  : voit uniquement si une journée est "occupée"
                      (réservation de salle validée), sans aucun détail,
                      + les activités publiques.
- Utilisateur connecté (non staff) : voit en plus les activités privées,
                      mais pas le détail des demandes de réservation.
- Administrateur (is_staff) : voit tout, y compris les demandes de
                      réservation en attente ou refusées et les coordonnées
                      des demandeurs.

Les activités et réservations couvrent une FOURCHETTE de dates
(date_debut / date_fin) : une même activité peut donc apparaître sur
plusieurs cases consécutives du calendrier.
"""
import calendar
from datetime import date

from .models import Activite, Reservation

# Le calendrier belge/français commence la semaine un lundi.
_CALENDRIER = calendar.Calendar(firstweekday=calendar.MONDAY)


def construire_semaines_du_mois(annee, mois, user):
    """Construit la grille du mois sous la forme d'une liste de semaines,
    chaque semaine étant une liste de 7 éléments (dict d'infos du jour, ou
    None si la case correspond à un jour hors du mois affiché)."""

    premier_jour_du_mois = date(annee, mois, 1)
    dernier_jour_du_mois = date(annee, mois, calendar.monthrange(annee, mois)[1])

    # --- Récupération des données du mois concerné -----------------------
    # Une activité/réservation "chevauche" le mois affiché dès que sa date
    # de début n'est pas après la fin du mois, ET que sa date de fin n'est
    # pas avant le début du mois (intersection de deux intervalles).
    activites_du_mois = Activite.objects.filter(
        date_debut__lte=dernier_jour_du_mois,
        date_fin__gte=premier_jour_du_mois,
    )

    # Un visiteur non connecté ou un utilisateur connecté "classique" ne
    # doit pas voir les activités privées des autres membres.
    utilisateur_administrateur = user.is_authenticated and user.is_staff
    if not user.is_authenticated:
        activites_du_mois = activites_du_mois.filter(visibilite=Activite.VISIBILITE_PUBLIQUE)
    elif not utilisateur_administrateur:
        # Connecté : publique + privée (le filtrage "privé" autorise déjà
        # tout utilisateur connecté, voir Activite.est_visible_par).
        pass

    reservations_du_mois = Reservation.objects.filter(
        date_debut__lte=dernier_jour_du_mois,
        date_fin__gte=premier_jour_du_mois,
    )

    activites_du_mois = list(activites_du_mois.select_related("auteur"))
    reservations_du_mois = list(reservations_du_mois)

    aujourdhui = date.today()
    semaines = []

    for semaine_brute in _CALENDRIER.monthdayscalendar(annee, mois):
        semaine = []
        for numero_jour in semaine_brute:
            if numero_jour == 0:
                # Case vide (jour appartenant au mois précédent/suivant)
                semaine.append(None)
                continue

            date_du_jour = date(annee, mois, numero_jour)

            # Une activité/réservation s'affiche sur ce jour si celui-ci
            # est compris dans sa fourchette [date_debut ; date_fin].
            activites_jour = [
                a for a in activites_du_mois if a.date_debut <= date_du_jour <= a.date_fin
            ]
            reservations_jour = [
                r for r in reservations_du_mois if r.date_debut <= date_du_jour <= r.date_fin
            ]

            reservation_validee = any(
                r.statut == Reservation.STATUT_VALIDEE for r in reservations_jour
            )

            # Un visiteur ou un membre "normal" ne voit jamais le détail
            # (coordonnées, statut) des demandes de réservation : seule
            # l'information "salle réservée" lui est utile.
            reservations_visibles = reservations_jour if utilisateur_administrateur else []

            semaine.append(
                {
                    "numero": numero_jour,
                    "date": date_du_jour,
                    "activites": activites_jour,
                    "reservations": reservations_visibles,
                    "salle_reservee": reservation_validee,
                    "est_aujourdhui": date_du_jour == aujourdhui,
                }
            )
        semaines.append(semaine)

    return semaines


def mois_adjacent(annee, mois, decalage):
    """Renvoie le tuple (annee, mois) correspondant au mois précédent
    (decalage=-1) ou suivant (decalage=+1) du couple (annee, mois) donné."""
    mois_index = mois - 1 + decalage  # index 0-11 pour faciliter le calcul
    nouvelle_annee = annee + mois_index // 12
    nouveau_mois = mois_index % 12 + 1
    return nouvelle_annee, nouveau_mois
