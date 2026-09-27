"""
theatre/placement.py
════════════════════
Module de génération du plan de salle et de placement automatique
des réservations pour l'application de gestion de théâtre.

Fonctionnalités :
  - Détermination de la configuration de salle selon le nombre d'inscrits
  - Scoring de placement (rangée souhaitée, avant/centre/arrière, gauche/milieu/droite)
  - Placement groupé par réservation (places contiguës sur une ou deux rangées)
  - Création des PlaceReservee et PlaceLibre en base de données
  - Utilitaires de recalcul du CA

Langue  : Français
"""

from __future__ import annotations

import logging
from copy        import copy
from dataclasses import dataclass, field
from typing      import Optional

from django.db        import transaction
from django.utils     import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTES DE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

# Scores de priorité pour le placement (score plus bas = meilleure priorité)
SCORE_RANGEE_ADJACENTE = 10      # par unité de distance à la rangée souhaitée
SCORE_PREF_GENERALE    = 100     # préférence avant/centre/arrière sans rangée exacte
SCORE_MULTI_RANGEES    = 1000    # pénalité pour un placement sur 2 rangées
SCORE_FALLBACK         = 9999    # placement forcé en dernier recours

# Priorité de traitement des réservations selon leur préférence de rangée
PRIORITE_RANGEE = {
    'avant'  : 0,
    'centre' : 1,
    ''       : 1,   # sans préférence = traité comme centre
    'arriere': 2,
}


# ══════════════════════════════════════════════════════════════════════════════
#  STRUCTURES DE DONNÉES INTERNES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Case:
    """
    Représente une case dans la grille de travail.
    numero = None signifie que la case est déjà attribuée à une réservation.
    """
    rangee  : int
    colonne : int
    numero  : Optional[int]   # None = occupée


@dataclass
class SnapshotPlace:
    """
    Copie immuable des données d'une case au moment de son attribution.
    Utilisée pour la sauvegarde en base APRÈS que appliquer_placement()
    a mis case.numero = None dans la grille.
    """
    rangee  : int
    colonne : int
    numero  : int             # toujours défini (jamais None)


@dataclass
class Placement:
    """
    Résultat d'un placement : liste de cases choisies + score associé.
    Les cases sont des COPIES indépendantes de la grille.
    """
    cases : list[Case]
    score : float = field(default=float(SCORE_FALLBACK))

    def __bool__(self) -> bool:
        return len(self.cases) > 0

    def snapshot(self) -> list[SnapshotPlace]:
        """
        Retourne un snapshot immuable des cases AVANT tout appel à
        appliquer_placement(). Lève ValueError si un numéro est None.
        """
        resultat = []
        for c in self.cases:
            if c.numero is None:
                raise ValueError(
                    f"Case ({c.rangee}, {c.colonne}) a numero=None dans le snapshot — "
                    "appliquer_placement() a été appelé trop tôt."
                )
            resultat.append(SnapshotPlace(
                rangee  = c.rangee,
                colonne = c.colonne,
                numero  = c.numero,
            ))
        return resultat


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION DE SALLE
# ══════════════════════════════════════════════════════════════════════════════

def determiner_configuration(nb_inscrits: int) -> list[int]:
    """
    Retourne la liste du nombre de places par rangée (de l'avant vers l'arrière)
    en fonction du nombre total de places réservées.

    Règles métier :
      ≤  80 inscrits → 10 rangées × 10 places          = 100 places
      ≤ 120 inscrits → 1×11 + 4×12 + 3×11 + 3×10      = 122 places
      >  120 inscrits → 1×14 + 4×15 + 1×14 + 2×15
                        + 3×14 + 1×12                  = 172 places

    Args:
        nb_inscrits : Nombre total de places réservées.

    Returns:
        Liste d'entiers (places par rangée).
    """
    if nb_inscrits <= 80:
        return [10] * 10

    if nb_inscrits <= 120:
        return [11] + [12] * 4 + [11] * 3 + [10] * 3

    return [14] + [15] * 4 + [14] + [15] * 2 + [14] * 3 + [12]


def creer_grille(config: list[int]) -> list[list[Case]]:
    """
    Construit la grille de travail à partir de la configuration de salle.
    La numérotation des places est continue, de gauche à droite et de
    l'avant vers l'arrière (place 1 = rangée 0, colonne 0).

    Args:
        config : Liste du nombre de places par rangée.

    Returns:
        Grille bidimensionnelle [rangee][colonne] de Case.
    """
    grille = []
    numero = 1

    for idx_r, nb_cols in enumerate(config):
        rangee = []
        for idx_c in range(nb_cols):
            rangee.append(Case(rangee=idx_r, colonne=idx_c, numero=numero))
            numero += 1
        grille.append(rangee)

    return grille


def cases_libres_rangee(grille: list[list[Case]], idx_rangee: int) -> list[Case]:
    """
    Retourne les cases encore libres (numero non None) d'une rangée,
    triées par colonne croissante.

    Args:
        grille     : Grille complète de la salle.
        idx_rangee : Index de la rangée à analyser.

    Returns:
        Liste des Case libres.
    """
    return [c for c in grille[idx_rangee] if c.numero is not None]


# ══════════════════════════════════════════════════════════════════════════════
#  FONCTIONS DE SCORING
# ══════════════════════════════════════════════════════════════════════════════

def score_rangee(
    idx_rangee       : int,
    nb_rangees       : int,
    preference_rangee: str,
    rangee_preferee  : str,
) -> float:
    """
    Calcule le score de priorité d'une rangée candidate.
    Score plus bas = meilleure adéquation avec les préférences du spectateur.

    Priorité 1 — Rangée souhaitée exacte (champ rangee_preferee, valeurs '1'–'6') :
        score = distance_à_la_rangée_souhaitée × SCORE_RANGEE_ADJACENTE
        → 0 si rangée exacte, 10 si 1 rangée d'écart, 20 si 2, etc.

    Priorité 2 — Préférence avant / centre / arrière (sans rangée exacte) :
        score = SCORE_PREF_GENERALE + position_relative_normalisée

    Args:
        idx_rangee        : Index 0-based de la rangée candidate.
        nb_rangees        : Nombre total de rangées dans la salle.
        preference_rangee : 'avant', 'centre', 'arriere' ou ''.
        rangee_preferee   : Numéro de rangée souhaitée ('1'–'6') ou ''.

    Returns:
        Score flottant ≥ 0.
    """
    # ── Priorité 1 : rangée souhaitée exacte ─────────────────────────────────
    if rangee_preferee:
        rang_souhaite = int(rangee_preferee) - 1       # index 0-based
        distance      = abs(idx_rangee - rang_souhaite)
        return float(distance * SCORE_RANGEE_ADJACENTE)

    # ── Priorité 2 : préférence avant / centre / arrière ─────────────────────
    # position_relative : 0.0 = première rangée (avant scène)
    #                     1.0 = dernière rangée (arrière salle)
    if nb_rangees <= 1:
        position_relative = 0.0
    else:
        position_relative = idx_rangee / (nb_rangees - 1)

    if preference_rangee == 'avant':
        score_pos = position_relative                  # petit index = bon score

    elif preference_rangee == 'arriere':
        score_pos = 1.0 - position_relative            # grand index = bon score

    else:
        # 'centre' ou '' : préfère les rangées proches du milieu de la salle
        score_pos = abs(position_relative - 0.5)

    return float(SCORE_PREF_GENERALE + score_pos)


def score_colonne(
    col_debut             : int,
    nb_cols_rangee        : int,
    nb_places_reservation : int,
    preference_cote       : str,
) -> float:
    """
    Calcule le score de position latérale d'un bloc dans une rangée.
    Score plus bas = meilleure adéquation avec la préférence de côté.

    Le "centre du bloc" est comparé au "centre de la rangée".

    Args:
        col_debut              : Colonne de départ du bloc (0-based).
        nb_cols_rangee         : Nombre total de colonnes dans la rangée.
        nb_places_reservation  : Largeur du bloc (nombre de places).
        preference_cote        : 'gauche', 'milieu', 'droite' ou ''.

    Returns:
        Score flottant ≥ 0.
    """
    centre_rangee = (nb_cols_rangee - 1) / 2.0
    centre_bloc   = col_debut + (nb_places_reservation - 1) / 2.0

    if preference_cote == 'gauche':
        return float(centre_bloc)                         # plus à gauche = mieux

    if preference_cote == 'droite':
        return float(nb_cols_rangee - centre_bloc)        # plus à droite = mieux

    # 'milieu' ou '' : préfère le centre de la rangée
    return float(abs(centre_bloc - centre_rangee))


# ══════════════════════════════════════════════════════════════════════════════
#  RECHERCHE DE BLOCS CONTIGUS
# ══════════════════════════════════════════════════════════════════════════════

def trouver_blocs_contigus(
    cases     : list[Case],
    nb_places : int,
) -> list[list[Case]]:
    """
    Cherche tous les blocs de `nb_places` cases contiguës (colonnes consécutives)
    dans une liste de cases libres.

    IMPORTANT : Retourne des COPIES indépendantes des cases pour éviter
    les effets de bord lors de l'appel ultérieur à appliquer_placement().

    Args:
        cases     : Cases libres d'une rangée, triées par colonne croissante.
        nb_places : Nombre de places consécutives requises.

    Returns:
        Liste de blocs valides. Chaque bloc est une liste de Case (copies).
        Liste vide si aucun bloc suffisant n'existe.
    """
    if len(cases) < nb_places:
        return []

    blocs_valides = []

    for i in range(len(cases) - nb_places + 1):
        candidat = cases[i: i + nb_places]
        colonnes  = [c.colonne for c in candidat]

        # Vérifie que les colonnes sont strictement consécutives
        if colonnes[-1] - colonnes[0] == nb_places - 1:
            # Copies indépendantes → appliquer_placement ne les affectera pas
            blocs_valides.append([copy(c) for c in candidat])

    return blocs_valides


# ══════════════════════════════════════════════════════════════════════════════
#  STRATÉGIES DE PLACEMENT
# ══════════════════════════════════════════════════════════════════════════════

def meilleur_bloc_rangee(
    grille           : list[list[Case]],
    config           : list[int],
    idx_rangee       : int,
    nb_places        : int,
    preference_rangee: str,
    rangee_preferee  : str,
    preference_cote  : str,
) -> Optional[Placement]:
    """
    Stratégie 1 — Bloc contigu sur une seule rangée (placement optimal).

    Recherche tous les blocs possibles dans la rangée et retourne celui
    qui minimise le score combiné (rangée + colonne).

    Args:
        grille            : Grille complète de la salle.
        config            : Nombre de places par rangée.
        idx_rangee        : Index de la rangée à tester.
        nb_places         : Nombre de places à placer.
        preference_rangee : Préférence avant/centre/arrière.
        rangee_preferee   : Numéro de rangée souhaitée ou ''.
        preference_cote   : Préférence gauche/milieu/droite.

    Returns:
        Meilleur Placement sur cette rangée, ou None si impossible.
    """
    libres = cases_libres_rangee(grille, idx_rangee)
    blocs  = trouver_blocs_contigus(libres, nb_places)

    if not blocs:
        return None

    sc_rangee = score_rangee(
        idx_rangee, len(config), preference_rangee, rangee_preferee
    )

    meilleur       : Optional[Placement] = None
    meilleur_score : float               = float('inf')

    for bloc in blocs:
        sc_col = score_colonne(
            col_debut             = bloc[0].colonne,
            nb_cols_rangee        = config[idx_rangee],
            nb_places_reservation = nb_places,
            preference_cote       = preference_cote,
        )
        score_total = sc_rangee + sc_col

        if score_total < meilleur_score:
            meilleur_score = score_total
            meilleur       = Placement(cases=bloc, score=score_total)

    return meilleur


def placer_sur_deux_rangees(
    grille            : list[list[Case]],
    config            : list[int],
    idx_rangee_debut  : int,
    nb_places         : int,
    preference_rangee : str,
    rangee_preferee   : str,
    preference_cote   : str,
) -> Optional[Placement]:
    """
    Stratégie 2 — Placement sur deux rangées consécutives (placement acceptable).

    Utilisée lorsque aucune rangée ne peut accueillir toutes les places en bloc.
    Privilégie l'alignement vertical des colonnes pour que les spectateurs
    d'un même groupe soient face à face.

    Pénalité : SCORE_MULTI_RANGEES ajouté au score final.

    Args:
        grille             : Grille complète.
        config             : Nombre de places par rangée.
        idx_rangee_debut   : Première rangée du duo.
        nb_places          : Nombre total de places à placer.
        preference_rangee  : Préférence avant/centre/arrière.
        rangee_preferee    : Numéro de rangée souhaitée ou ''.
        preference_cote    : Préférence gauche/milieu/droite.

    Returns:
        Placement sur 2 rangées avec copies des cases, ou None si impossible.
    """
    idx_r2 = idx_rangee_debut + 1
    if idx_r2 >= len(grille):
        return None

    libres_r1 = cases_libres_rangee(grille, idx_rangee_debut)
    libres_r2 = cases_libres_rangee(grille, idx_r2)

    if not libres_r1 or not libres_r2:
        return None

    # Index des colonnes libres dans chaque rangée
    cols_r1 = {c.colonne: c for c in libres_r1}
    cols_r2 = {c.colonne: c for c in libres_r2}

    # Colonnes communes aux deux rangées (alignement vertical garanti)
    cols_communes = sorted(set(cols_r1.keys()) & set(cols_r2.keys()))
    if not cols_communes:
        return None

    # Cases communes de chaque rangée, triées par colonne
    communes_r1 = [cols_r1[c] for c in cols_communes]
    communes_r2 = [cols_r2[c] for c in cols_communes]

    meilleur       : Optional[Placement] = None
    meilleur_score : float               = float('inf')

    # Teste tous les blocs possibles dans r1 parmi les colonnes communes
    for taille_r1 in range(1, min(nb_places, len(communes_r1)) + 1):
        taille_r2 = nb_places - taille_r1

        if taille_r2 <= 0 or taille_r2 > len(communes_r2):
            continue

        blocs_r1 = trouver_blocs_contigus(communes_r1, taille_r1)
        blocs_r2 = trouver_blocs_contigus(communes_r2, taille_r2)

        if not blocs_r1 or not blocs_r2:
            continue

        for bloc_r1 in blocs_r1:
            for bloc_r2 in blocs_r2:
                # Vérifie qu'il n'y a pas de doublons de numéros
                numeros = {c.numero for c in bloc_r1} | {c.numero for c in bloc_r2}
                if len(numeros) != nb_places:
                    continue

                toutes_cases = bloc_r1 + bloc_r2   # déjà des copies

                sc_rangee = score_rangee(
                    idx_rangee_debut, len(config),
                    preference_rangee, rangee_preferee
                )
                sc_col = score_colonne(
                    col_debut             = bloc_r1[0].colonne,
                    nb_cols_rangee        = config[idx_rangee_debut],
                    nb_places_reservation = taille_r1,
                    preference_cote       = preference_cote,
                )
                score_total = SCORE_MULTI_RANGEES + sc_rangee + sc_col

                if score_total < meilleur_score:
                    meilleur_score = score_total
                    meilleur       = Placement(cases=toutes_cases, score=score_total)

    return meilleur


def placement_force(
    grille    : list[list[Case]],
    nb_places : int,
) -> Optional[Placement]:
    """
    Stratégie 3 — Placement de dernier recours (fallback).

    Prend les premières cases libres disponibles dans la grille,
    sans tenir compte des préférences ni de la contiguïté.

    IMPORTANT : Retourne des COPIES indépendantes des cases.

    Args:
        grille    : Grille complète.
        nb_places : Nombre de places nécessaires.

    Returns:
        Placement avec les premières cases disponibles, ou None si
        la salle ne peut plus accueillir ce groupe.
    """
    cases_trouvees : list[Case] = []

    for rangee in grille:
        for case in rangee:
            if case.numero is not None:
                cases_trouvees.append(copy(case))   # copie indépendante
                if len(cases_trouvees) == nb_places:
                    return Placement(
                        cases = cases_trouvees,
                        score = float(SCORE_FALLBACK),
                    )

    logger.warning(
        "Placement forcé impossible : %d places demandées, "
        "seulement %d disponibles dans toute la salle.",
        nb_places, len(cases_trouvees)
    )
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  ALGORITHME PRINCIPAL DE RECHERCHE
# ══════════════════════════════════════════════════════════════════════════════

def trouver_meilleur_placement(
    grille           : list[list[Case]],
    config           : list[int],
    nb_places        : int,
    preference_rangee: str,
    rangee_preferee  : str,
    preference_cote  : str,
) -> Optional[Placement]:
    """
    Recherche le meilleur placement pour un groupe de `nb_places` places.

    Algorithme en trois passes successives :
      Passe 1 — Bloc contigu sur une seule rangée (optimal).
                Les rangées sont évaluées dans l'ordre de leur score.
                Dès qu'un bloc est trouvé sur la rangée la mieux scorée,
                on s'arrête (aucune rangée suivante ne peut faire mieux).

      Passe 2 — Placement sur deux rangées consécutives (acceptable).
                Pénalisé par SCORE_MULTI_RANGEES pour qu'il ne soit
                choisi qu'en l'absence d'alternative sur une rangée unique.

      Passe 3 — Placement forcé sur les premières places libres (dernier recours).
                Utilisé uniquement lorsque la salle est très fragmentée.

    Args:
        grille            : Grille de travail courante.
        config            : Nombre de places par rangée.
        nb_places         : Nombre de places à placer.
        preference_rangee : 'avant', 'centre', 'arriere' ou ''.
        rangee_preferee   : Numéro de rangée souhaitée ('1'–'6') ou ''.
        preference_cote   : 'gauche', 'milieu', 'droite' ou ''.

    Returns:
        Meilleur Placement trouvé (cases = copies indépendantes),
        ou None si la salle est pleine.
    """
    nb_rangees = len(grille)

    # Tri des rangées par score croissant (meilleure candidate en tête)
    rangees_par_score = sorted(
        range(nb_rangees),
        key=lambda i: score_rangee(
            i, nb_rangees, preference_rangee, rangee_preferee
        )
    )

    # ── Passe 1 : bloc contigu sur une seule rangée ──────────────────────────
    for idx_r in rangees_par_score:
        placement = meilleur_bloc_rangee(
            grille, config, idx_r, nb_places,
            preference_rangee, rangee_preferee, preference_cote,
        )
        if placement:
            logger.debug(
                "Passe 1 réussie : rangée %d, score %.2f, places %s.",
                idx_r, placement.score,
                [c.numero for c in placement.cases]
            )
            return placement

    # ── Passe 2 : deux rangées consécutives ──────────────────────────────────
    meilleur_multi : Optional[Placement] = None

    for idx_r in rangees_par_score:
        placement = placer_sur_deux_rangees(
            grille, config, idx_r, nb_places,
            preference_rangee, rangee_preferee, preference_cote,
        )
        if placement:
            if meilleur_multi is None or placement.score < meilleur_multi.score:
                meilleur_multi = placement

    if meilleur_multi:
        logger.debug(
            "Passe 2 réussie : score %.2f, places %s.",
            meilleur_multi.score,
            [c.numero for c in meilleur_multi.cases]
        )
        return meilleur_multi

    # ── Passe 3 : placement forcé ─────────────────────────────────────────────
    logger.warning(
        "Passes 1 et 2 échouées pour %d places "
        "(pref_rangée='%s', rangée_souhaitée='%s'). "
        "Tentative de placement forcé.",
        nb_places, preference_rangee, rangee_preferee
    )
    return placement_force(grille, nb_places)


def appliquer_placement(
    grille    : list[list[Case]],
    placement : Placement,
) -> None:
    """
    Marque les cases du placement comme occupées dans la grille
    en mettant leur numéro à None.

    IMPORTANT : Appeler cette fonction UNIQUEMENT après avoir extrait
    le snapshot via placement.snapshot(), car elle efface les numéros.

    Args:
        grille    : Grille à modifier en place.
        placement : Placement dont les cases doivent être marquées occupées.
    """
    for case in placement.cases:
        cellule = grille[case.rangee][case.colonne]
        if cellule.numero is None:
            logger.warning(
                "Case (%d, %d) déjà occupée lors de appliquer_placement "
                "— doublon possible.",
                case.rangee, case.colonne
            )
        cellule.numero = None


# ══════════════════════════════════════════════════════════════════════════════
#  TRI DES RÉSERVATIONS
# ══════════════════════════════════════════════════════════════════════════════

def trier_reservations(reservations: list) -> list:
    """
    Trie les réservations dans l'ordre de traitement pour le placement.

    Critères (priorité décroissante) :
      1. Réservations avec rangée souhaitée en premier
         (contrainte forte à satisfaire avant les autres).
      2. Préférence de rangée : avant > centre/neutre > arrière
         (les spectateurs de l'avant ont accès aux meilleures places en premier).
      3. Date d'inscription croissante (FIFO) :
         les premiers inscrits ont priorité sur les meilleures places.

    Args:
        reservations : Liste d'objets Reservation Django.

    Returns:
        Nouvelle liste triée (l'originale n'est pas modifiée).
    """
    def cle_tri(reservation):
        a_rangee_souhaitee = 0 if reservation.rangee_preferee else 1
        prio_rangee        = PRIORITE_RANGEE.get(
            reservation.preference_rangee or '', 1
        )
        return (a_rangee_souhaitee, prio_rangee, reservation.created_at)

    return sorted(reservations, key=cle_tri)


# ══════════════════════════════════════════════════════════════════════════════
#  FONCTION PRINCIPALE : GÉNÉRATION DU PLAN DE SALLE
# ══════════════════════════════════════════════════════════════════════════════

@transaction.atomic
def placer_reservations(representation):
    """
    Point d'entrée principal.

    Génère ou regénère complètement le plan de salle pour une représentation :
      1. Calcule la configuration de salle adaptée au nombre d'inscrits.
      2. Supprime l'ancien plan (cascade sur PlaceReservee, PlaceLibre,
         ZoneTampon, Ticket).
      3. Construit la grille de travail en mémoire.
      4. Trie les réservations selon les critères de priorité.
      5. Pour chaque réservation, recherche le meilleur placement en 3 passes.
      6. Extrait un snapshot AVANT d'appliquer le placement dans la grille.
      7. Crée les PlaceReservee en base à partir des snapshots.
      8. Crée les PlaceLibre pour toutes les cases non attribuées
         (disponibles pour la vente flash lors du contrôle d'entrée).

    La transaction atomique garantit qu'en cas d'erreur, aucune donnée
    partielle n'est enregistrée en base.

    Args:
        representation : Instance du modèle Representation Django.

    Returns:
        Instance du modèle PlanSalle nouvellement créé.

    Raises:
        Exception : Toute erreur annule la transaction (rollback complet).
    """
    # Import local pour éviter les imports circulaires avec models.py
    from .models import (
        PlanSalle, PlaceReservee, PlaceLibre, Reservation,
    )

    logger.info(
        "=== Début génération plan de salle : '%s' (pk=%d) ===",
        representation.nom, representation.pk
    )

    # ── 1. Récupération des réservations ─────────────────────────────────────
    reservations = list(
        Reservation.objects
        .filter(representation=representation)
        .order_by('created_at')
    )

    nb_inscrits = sum(r.total_places() for r in reservations)

    logger.info(
        "%d réservation(s), %d place(s) à placer.",
        len(reservations), nb_inscrits
    )

    # ── 2. Configuration de salle ─────────────────────────────────────────────
    config   = determiner_configuration(nb_inscrits)
    nb_total = sum(config)

    logger.info(
        "Configuration : %d rangées, %d places. Détail : %s",
        len(config), nb_total, config
    )

    # ── 3. Suppression de l'ancien plan (CASCADE) ────────────────────────────
    ancien = PlanSalle.objects.filter(representation=representation).first()
    if ancien:
        logger.info("Suppression de l'ancien plan (pk=%d).", ancien.pk)
        ancien.delete()

    # ── 4. Création du nouveau plan ───────────────────────────────────────────
    plan = PlanSalle.objects.create(
        representation  = representation,
        nb_rangees      = len(config),
        configuration   = config,
        nb_total_places = nb_total,
    )
    logger.info("Nouveau PlanSalle créé (pk=%d).", plan.pk)

    # ── 5. Grille de travail en mémoire ──────────────────────────────────────
    grille = creer_grille(config)

    # ── 6. Tri des réservations ───────────────────────────────────────────────
    reservations_triees = trier_reservations(reservations)

    # ── 7. Placement de chaque réservation ───────────────────────────────────
    # Accumulation des snapshots pour le bulk_create final
    snapshots_par_reservation : list[tuple] = []
    # tuple = (reservation, [SnapshotPlace, ...])

    nb_non_places = 0

    for res in reservations_triees:
        nb_places = res.total_places()

        if nb_places == 0:
            logger.debug("Réservation pk=%d ignorée (0 places).", res.pk)
            continue

        # Recherche du meilleur placement (3 passes)
        placement = trouver_meilleur_placement(
            grille            = grille,
            config            = config,
            nb_places         = nb_places,
            preference_rangee = res.preference_rangee or '',
            rangee_preferee   = res.rangee_preferee   or '',
            preference_cote   = res.preference_cote   or '',
        )

        if not placement:
            logger.error(
                "Réservation pk=%d (%s %s, %d places) : "
                "IMPOSSIBLE À PLACER (salle pleine ?).",
                res.pk, res.nom, res.prenom, nb_places
            )
            nb_non_places += 1
            continue

        # ── CRITIQUE : snapshot AVANT appliquer_placement ────────────────────
        # Les cases dans placement.cases sont des COPIES de la grille,
        # mais on extrait quand même le snapshot ici pour sécurité absolue.
        try:
            snap = placement.snapshot()
        except ValueError as exc:
            logger.error(
                "Snapshot invalide pour réservation pk=%d : %s. "
                "Réservation ignorée.",
                res.pk, exc
            )
            nb_non_places += 1
            continue

        # Vérifie qu'aucun numéro n'est None dans le snapshot
        numeros_snap = [s.numero for s in snap]
        if any(n is None for n in numeros_snap):
            logger.error(
                "Réservation pk=%d : snapshot contient des numéros None %s. "
                "Réservation ignorée.",
                res.pk, numeros_snap
            )
            nb_non_places += 1
            continue

        # Stocke le snapshot pour le bulk_create
        snapshots_par_reservation.append((res, snap))

        # Marque les cases comme occupées dans la grille de travail
        # (après le snapshot → les numéros sont déjà sauvegardés)
        appliquer_placement(grille, placement)

        logger.debug(
            "Réservation pk=%d (%s %s) → places %s (score=%.2f).",
            res.pk, res.nom, res.prenom, numeros_snap, placement.score
        )

    # ── 8. Création en base des PlaceReservee ─────────────────────────────────
    places_reservees = [
        PlaceReservee(
            plan_salle   = plan,
            reservation  = res,
            numero_place = snap.numero,   # ← depuis le snapshot, jamais None
            rangee       = snap.rangee,
            colonne      = snap.colonne,
        )
        for res, snaps in snapshots_par_reservation
        for snap in snaps
    ]

    if places_reservees:
        PlaceReservee.objects.bulk_create(places_reservees)
        logger.info("%d PlaceReservee créées.", len(places_reservees))

    # ── 9. Création en base des PlaceLibre ────────────────────────────────────
    # Toutes les cases dont grille[r][c].numero n'est PAS None après le placement
    # sont des places non attribuées → disponibles pour la vente flash.
    places_libres = [
        PlaceLibre(
            plan_salle   = plan,
            numero_place = case.numero,   # ← jamais None ici (cases non occupées)
            rangee       = case.rangee,
            colonne      = case.colonne,
            statut       = 'libre',
        )
        for rangee in grille
        for case in rangee
        if case.numero is not None
    ]

    if places_libres:
        PlaceLibre.objects.bulk_create(places_libres)
        logger.info(
            "%d PlaceLibre créées (disponibles pour vente flash).",
            len(places_libres)
        )

    # ── 10. Rapport final ─────────────────────────────────────────────────────
    logger.info(
        "=== Plan finalisé : %d place(s) attribuée(s), "
        "%d place(s) libre(s), %d réservation(s) non placée(s). ===",
        len(places_reservees),
        len(places_libres),
        nb_non_places,
    )

    if nb_non_places > 0:
        logger.warning(
            "%d réservation(s) non placée(s). "
            "Vérifiez la capacité de la salle ou les données.",
            nb_non_places
        )

    return plan


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITAIRES CHIFFRE D'AFFAIRES
# ══════════════════════════════════════════════════════════════════════════════

def calculer_ca_total(plan) -> float:
    """
    Calcule le chiffre d'affaires total d'un plan de salle :
    tickets valides (entrées validées) + ventes flash valides.

    Args:
        plan : Instance du modèle PlanSalle.

    Returns:
        Montant total en euros (float).
    """
    from .models import Ticket, VenteFlash

    ca_tickets = sum(
        float(t.prix_unitaire)
        for t in Ticket.objects.filter(
            place__plan_salle = plan,
            statut            = 'valide',
        )
    )

    ca_flash = sum(
        float(v.prix)
        for v in VenteFlash.objects.filter(
            place_libre__plan_salle = plan,
            statut                  = 'valide',
        )
    )

    return ca_tickets + ca_flash


def calculer_ca_representation(representation) -> float:
    """
    Calcule le CA total pour une représentation.
    Retourne 0.0 si aucun plan n'existe encore.

    Args:
        representation : Instance du modèle Representation Django.

    Returns:
        Montant total en euros (float).
    """
    from .models import PlanSalle

    plan = PlanSalle.objects.filter(representation=representation).first()
    return calculer_ca_total(plan) if plan else 0.0