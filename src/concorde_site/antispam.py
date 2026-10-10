"""
Protection anti-spam des formulaires publics (newsletter, demande de
réservation de salle, contact).

Deux mécanismes, sans service externe ni captcha :

- Champ piège : un champ invisible pour les humains (gabarit
  includes/champ_piege.html), que les robots remplissent. Un envoi qui le
  contient est ignoré, mais on répond comme si tout s'était bien passé pour
  ne pas apprendre au robot qu'il a été repéré.
- Limite par adresse IP : au plus N envois réussis par heure, comptés dans
  le cache partagé entre les processus (voir CACHES dans settings/base.py).
"""
from django.core.cache import cache

# Nom anglais volontaire : un champ « Website » est rempli d'office par les
# robots, et il ne peut pas entrer en conflit avec un champ du formulaire de
# contact créé dans l'admin (libellés en français).
CHAMP_PIEGE = "website"

DUREE_LIMITE = 3600  # secondes


def ip_client(request):
    # Pas de X-Forwarded-For : l'en-tête est fourni par le visiteur lui-même,
    # qui pourrait changer de valeur à chaque requête et contourner la limite.
    # Sur o2switch, Apache/Passenger renseigne REMOTE_ADDR avec l'IP réelle.
    return request.META.get("REMOTE_ADDR", "")


def est_un_robot(request):
    return bool(request.POST.get(CHAMP_PIEGE))


def _cle(request, prefixe):
    return f"{prefixe}-{ip_client(request)}"


def limite_atteinte(request, prefixe, limite):
    return cache.get(_cle(request, prefixe), 0) >= limite


def compter_envoi(request, prefixe):
    """À appeler après un envoi réussi (les erreurs de saisie ne comptent pas)."""
    cle = _cle(request, prefixe)
    # add() crée le compteur (expiration 1 h à partir du premier envoi) ;
    # incr() l'augmente sans repousser cette échéance.
    if not cache.add(cle, 1, DUREE_LIMITE):
        cache.incr(cle)
