"""
Recopie du calendrier dans un agenda Google Workspace partagé.

Sens unique : le site reste la référence. Chaque activité (publique ou
privée) et chaque location VALIDÉE devient un événement « toute la
journée » de l'agenda ; une location refusée, annulée (statut ou contrat
annulé) ou supprimée en est retirée. Un événement modifié ou supprimé à la
main dans Google est remis en état à la synchronisation suivante.

L'écriture passe par un compte de service Google (clé JSON) avec lequel
l'agenda est partagé, voir DEPLOIEMENT_O2SWITCH.md. Sans GOOGLE_AGENDA_ID
ou GOOGLE_AGENDA_CLE dans le .env, rien n'est envoyé.

Une panne de Google n'empêche jamais d'enregistrer sur le site : l'erreur
est journalisée, et la commande synchroniser_agenda_google (tâche cron de
nuit) rattrape les écarts.
"""
import logging
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings

logger = logging.getLogger("calendrier")

API = "https://www.googleapis.com/calendar/v3/calendars/{agenda}/events"
PORTEE = "https://www.googleapis.com/auth/calendar.events"
DELAI = 15  # secondes, par requête

# Marque posée sur les événements créés par le site : seuls ceux-là sont
# modifiés ou supprimés, jamais les événements ajoutés à la main dans Google.
MARQUE = "concorde_site"

COULEUR_LOCATION = "11"  # rouge tomate (palette fixe de Google Agenda)
COULEUR_PRIVEE = "8"  # graphite

_session = None
derniere_erreur = ""


def actif():
    return bool(settings.GOOGLE_AGENDA_ID and settings.GOOGLE_AGENDA_CLE)


def session():
    """Session HTTP authentifiée (le jeton est renouvelé automatiquement)."""
    global _session
    if _session is None:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account

        identifiants = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_AGENDA_CLE, scopes=[PORTEE]
        )
        _session = AuthorizedSession(identifiants)
    return _session


def _url(event_id=""):
    url = API.format(agenda=quote(settings.GOOGLE_AGENDA_ID, safe=""))
    return f"{url}/{quote(event_id, safe='')}" if event_id else url


def cle(objet):
    """Identifiant de l'objet du site, enregistré dans l'événement."""
    return f"{type(objet).__name__.lower()}-{objet.pk}"


def doit_figurer(objet):
    from .models import Reservation

    return not isinstance(objet, Reservation) or objet.statut == Reservation.STATUT_VALIDEE


def evenement(objet):
    """Contenu de l'événement Google. Une location n'y montre que le nom du
    client : ses coordonnées restent sur le site."""
    from .models import Activite

    adresse = settings.WAGTAILADMIN_BASE_URL.rstrip("/") + objet.get_absolute_url()
    if isinstance(objet, Activite):
        prive = objet.visibilite == Activite.VISIBILITE_PRIVEE
        titre = f"{objet.nom} (privée)" if prive else objet.nom
        details = objet.description
        couleur = COULEUR_PRIVEE if prive else None
    else:
        titre = f"Location de salle — {objet.nom_court}"
        details = f"Demande n° {objet.pk}"
        couleur = COULEUR_LOCATION
    donnees = {
        "summary": titre,
        "description": f"{details}\n\n{adresse}".strip(),
        # Événement « toute la journée » : Google attend le lendemain du
        # dernier jour comme fin.
        "start": {"date": objet.date_debut.isoformat()},
        "end": {"date": (objet.date_fin + timedelta(days=1)).isoformat()},
        "extendedProperties": {"private": {MARQUE: cle(objet)}},
        "transparency": "transparent",  # n'occupe pas l'agenda des membres
    }
    if couleur:
        donnees["colorId"] = couleur
    return donnees


class ErreurGoogle(Exception):
    pass


def _verifier(reponse):
    """Comme raise_for_status(), avec l'explication donnée par Google."""
    if reponse.status_code >= 400:
        try:
            detail = reponse.json()["error"]["message"]
        except Exception:
            detail = reponse.text[:300]
        raise ErreurGoogle(f"HTTP {reponse.status_code} : {detail}")


def _enregistrer_id(objet, event_id):
    objet.google_event_id = event_id
    # update() plutôt que save() : ne relance pas la synchronisation
    type(objet).objects.filter(pk=objet.pk).update(google_event_id=event_id)


def _envoyer(objet):
    if not doit_figurer(objet):
        if objet.google_event_id:
            _supprimer(objet.google_event_id)
            _enregistrer_id(objet, "")
        return
    if objet.google_event_id:
        reponse = session().put(_url(objet.google_event_id), json=evenement(objet), timeout=DELAI)
        # Supprimé à la main dans Google : recréé ci-dessous
        if reponse.status_code not in (404, 410):
            _verifier(reponse)
            if reponse.json().get("status") != "cancelled":
                return
    reponse = session().post(_url(), json=evenement(objet), timeout=DELAI)
    _verifier(reponse)
    _enregistrer_id(objet, reponse.json()["id"])


def _supprimer(event_id):
    reponse = session().delete(_url(event_id), timeout=DELAI)
    if reponse.status_code not in (404, 410):  # déjà supprimé
        _verifier(reponse)


def synchroniser(objet):
    """Crée, met à jour ou retire l'événement de l'objet. Renvoie False en
    cas d'échec (journalisé), True sinon."""
    if not actif():
        return True
    global derniere_erreur
    try:
        _envoyer(objet)
        return True
    except Exception as erreur:
        derniere_erreur = f"{objet} : {erreur}"
        logger.exception("Agenda Google : échec de la synchronisation de « %s »", objet)
        return False


def supprimer(event_id):
    """Retire un événement (objet supprimé du site)."""
    if not (actif() and event_id):
        return True
    global derniere_erreur
    try:
        _supprimer(event_id)
        return True
    except Exception as erreur:
        derniere_erreur = f"événement {event_id} : {erreur}"
        logger.exception("Agenda Google : échec de la suppression de l'événement %s", event_id)
        return False


def evenements_du_site():
    """Événements de l'agenda créés par le site : {event_id: clé}."""
    # Google ne sait filtrer que sur « marque=valeur » : on parcourt tous les
    # événements et on garde ceux qui portent la marque.
    resultat, page = {}, None
    while True:
        parametres = {"maxResults": 2500}
        if page:
            parametres["pageToken"] = page
        reponse = session().get(_url(), params=parametres, timeout=DELAI)
        _verifier(reponse)
        donnees = reponse.json()
        for item in donnees.get("items", []):
            marque = item.get("extendedProperties", {}).get("private", {}).get(MARQUE)
            if marque:
                resultat[item["id"]] = marque
        page = donnees.get("nextPageToken")
        if not page:
            return resultat
