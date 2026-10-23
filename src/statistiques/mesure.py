"""
Enregistrement des visites (appelé par le middleware après chaque page).

Ne compte que les pages HTML réellement affichées (GET, réponse 200) aux
visiteurs du site public : ni l'administration, ni les fichiers, ni les
robots d'indexation, ni les membres de l'équipe connectés (statut équipe),
qui fausseraient les chiffres en travaillant sur le site.
"""
import hashlib
import logging
import re
import secrets
from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from concorde_site.antispam import ip_client

from .models import EmpreinteDuJour, Jour, PageJour, ProvenanceJour, SelDuJour

logger = logging.getLogger(__name__)

PREFIXES_EXCLUS = (
    "/admin/", "/django-admin/", "/documents/", "/static/", "/media/", "/nl/", "/__debug__/",
    "/planning/",  # espace privé des membres
    "/inscription/",  # le lien d'invitation est personnel
)
_RE_ROBOT = re.compile(
    r"bot|crawl|spider|slurp|scrap|fetch|preview|monitor|uptime|headless|lighthouse|"
    r"curl|wget|python|java/|go-http|okhttp|axios|node-fetch|facebookexternalhit|whatsapp|"
    r"embedly|pingdom|semrush|ahrefs",
    re.IGNORECASE,
)
_RE_MOBILE = re.compile(r"Mobi|Android|iPhone|iPad", re.IGNORECASE)

# Sites d'origine connus, regroupés sous un nom lisible (le premier qui
# correspond l'emporte)
SOURCES = [
    ("mail.google.", "Gmail"),
    ("google.", "Google"),
    ("bing.", "Bing"),
    ("duckduckgo.", "DuckDuckGo"),
    ("facebook.", "Facebook"),
    ("fb.", "Facebook"),
    ("instagram.", "Instagram"),
    ("linkedin.", "LinkedIn"),
    ("lnkd.in", "LinkedIn"),
    ("t.co", "X (Twitter)"),
    ("twitter.", "X (Twitter)"),
    ("x.com", "X (Twitter)"),
    ("youtube.", "YouTube"),
    ("outlook.", "Outlook"),
]

# (date, sel) du jour, gardé en mémoire pour éviter une requête par visite
_sel = None


def a_compter(request, response):
    if request.method != "GET" or response.status_code != 200:
        return False
    if getattr(response, "streaming", False) or "text/html" not in response.get("Content-Type", ""):
        return False
    if request.path.startswith(PREFIXES_EXCLUS):
        return False
    # Pages préchargées par le navigateur, et appels JavaScript
    if request.headers.get("Sec-Purpose", "") or request.headers.get("Purpose", "") == "prefetch":
        return False
    if request.headers.get("X-Requested-With"):
        return False
    navigateur = request.META.get("HTTP_USER_AGENT", "")
    if not navigateur or _RE_ROBOT.search(navigateur):
        return False
    utilisateur = getattr(request, "user", None)
    return not (utilisateur and utilisateur.is_authenticated and utilisateur.is_staff)


def source(request):
    """Site d'où vient le visiteur, ou "" (accès direct, lien interne)."""
    hote = (urlsplit(request.META.get("HTTP_REFERER", "")).hostname or "").lower()
    if not hote:
        return ""
    for prefixe in ("www.", "m.", "l.", "lm.", "mobile."):
        hote = hote.removeprefix(prefixe)
    if hote == request.get_host().split(":")[0].lower().removeprefix("www."):
        return ""
    for debut, nom in SOURCES:
        if hote.startswith(debut) or f".{debut}" in f".{hote}":
            return nom
    return hote[:100]


def _purger(aujourdhui):
    """Le premier passage de la journée efface les empreintes de la veille,
    et les statistiques plus anciennes que la durée de conservation."""
    SelDuJour.objects.filter(date__lt=aujourdhui).delete()
    EmpreinteDuJour.objects.filter(date__lt=aujourdhui).delete()
    limite = aujourdhui - timedelta(days=settings.STATISTIQUES_CONSERVATION_JOURS)
    for modele in (Jour, PageJour, ProvenanceJour):
        modele.objects.filter(date__lt=limite).delete()


def sel_du_jour(aujourdhui):
    global _sel
    if _sel is None or _sel[0] != aujourdhui:
        objet, cree = SelDuJour.objects.get_or_create(date=aujourdhui, defaults={"sel": secrets.token_hex(32)})
        if cree:
            _purger(aujourdhui)
        _sel = (aujourdhui, objet.sel)
    return _sel[1]


def _ajouter(modele, cles, **increments):
    """Ajoute les increments à la ligne (créée au besoin)."""
    maj = {champ: F(champ) + valeur for champ, valeur in increments.items()}
    if modele.objects.filter(**cles).update(**maj):
        return
    try:
        with transaction.atomic():
            modele.objects.create(**cles, **increments)
    except IntegrityError:  # créée entre-temps par une autre requête
        modele.objects.filter(**cles).update(**maj)


def _nouveau_visiteur(request, aujourdhui):
    donnees = f"{sel_du_jour(aujourdhui)}|{ip_client(request)}|{request.META.get('HTTP_USER_AGENT', '')}"
    empreinte = hashlib.sha256(donnees.encode()).hexdigest()
    try:
        with transaction.atomic():
            EmpreinteDuJour.objects.create(date=aujourdhui, empreinte=empreinte)
        return True
    except IntegrityError:  # déjà venu aujourd'hui
        return False


def enregistrer(request):
    aujourdhui = timezone.localdate()
    mobile = bool(_RE_MOBILE.search(request.META.get("HTTP_USER_AGENT", "")))
    _ajouter(
        Jour, {"date": aujourdhui},
        vues=1, vues_mobiles=int(mobile), visiteurs=int(_nouveau_visiteur(request, aujourdhui)),
    )
    _ajouter(PageJour, {"date": aujourdhui, "chemin": request.path[:255]}, vues=1)
    origine = source(request)
    if origine:
        _ajouter(ProvenanceJour, {"date": aujourdhui, "source": origine}, vues=1)


def mesurer(request, response):
    """Une erreur de mesure ne doit jamais empêcher d'afficher la page."""
    try:
        if a_compter(request, response):
            enregistrer(request)
    except Exception:
        logger.exception("Statistiques : visite non enregistrée")
