"""
Tableau des tâches d'un événement : une colonne par tâche (bar, caisse…),
une ligne par horaire, une case par créneau.

Les lignes sont calculées à partir des débuts et fins de tous les créneaux :
chaque intervalle entre deux bornes consécutives devient une ligne, s'il est
couvert par au moins un créneau. Un créneau plus long que les autres
(montage 14 h–17 h face à des créneaux de 2 h) s'étend donc sur plusieurs
lignes. Les cases d'une tâche hors de ses plages horaires sont grisées.

Deux créneaux d'une même tâche qui se chevauchent (découpages superposés)
ne tiennent pas dans une seule colonne : la tâche reçoit une colonne de plus.
"""
from django.utils import timezone


def libelle_tache(creneau):
    return creneau.libelle or "Bénévoles"


def construire(creneaux):
    """Renvoie {"colonnes": [...], "lignes": [...]} ou None sans créneau.

    colonnes : [{"tache": "Bar", "libelle": "Bar", "suite": False}, …]
               (suite : deuxième colonne d'une même tâche)
    lignes   : [{"debut", "fin", "nouveau_jour", "cases": [case, …]}, …]
    case     : {"creneau": c, "hauteur": n} | {"vide": True} ; une case
               couverte par un créneau commencé plus haut est absente
               (la cellule du dessus s'étend sur elle, rowspan).
    """
    creneaux = sorted(creneaux, key=lambda c: (c.debut, c.fin))
    if not creneaux:
        return None
    bornes = sorted({c.debut for c in creneaux} | {c.fin for c in creneaux})
    segments = [
        (debut, fin) for debut, fin in zip(bornes, bornes[1:])
        if any(c.debut <= debut and c.fin >= fin for c in creneaux)
    ]
    rang = {debut: i for i, (debut, _) in enumerate(segments)}

    # Colonnes : une par tâche, dans l'ordre de leur premier créneau
    colonnes = []  # {"tache", "suite", "occupe": set(), "debuts": {indice: (creneau, hauteur)}}
    for c in creneaux:
        premier = rang[c.debut]
        couverts = {i for i, (debut, fin) in enumerate(segments) if c.debut <= debut and fin <= c.fin}
        tache = libelle_tache(c)
        colonne = next((col for col in colonnes if col["tache"] == tache and not col["occupe"] & couverts), None)
        if colonne is None:
            colonne = {"tache": tache, "libelle": c.libelle, "suite": any(col["tache"] == tache for col in colonnes),
                       "occupe": set(), "debuts": {}}
            colonnes.append(colonne)
        colonne["occupe"] |= couverts
        colonne["debuts"][premier] = (c, len(couverts))
    # Les colonnes d'une même tâche côte à côte
    ordre = {}
    for col in colonnes:
        ordre.setdefault(col["tache"], len(ordre))
    colonnes.sort(key=lambda col: ordre[col["tache"]])

    lignes, jour_precedent = [], None
    for i, (debut, fin) in enumerate(segments):
        cases = []
        for col in colonnes:
            if i in col["debuts"]:
                creneau, hauteur = col["debuts"][i]
                cases.append({"creneau": creneau, "hauteur": hauteur})
            elif i not in col["occupe"]:
                cases.append({"vide": True})
        jour = timezone.localtime(debut).date()
        lignes.append({"debut": debut, "fin": fin, "nouveau_jour": jour != jour_precedent, "cases": cases})
        jour_precedent = jour
    return {
        "colonnes": [{"tache": col["tache"], "libelle": col["libelle"], "suite": col["suite"]} for col in colonnes],
        "lignes": lignes,
        "plusieurs_jours": len({timezone.localtime(l["debut"]).date() for l in lignes}) > 1,
    }
