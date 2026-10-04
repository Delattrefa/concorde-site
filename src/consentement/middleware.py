"""
Bloque les contenus intégrés de sites tiers tant que l'internaute ne les a
pas acceptés.

Sur chaque page HTML du site public, l'adresse des <iframe> pointant vers
un autre site (Google Maps, YouTube, Vimeo, Facebook...) est déplacée de
l'attribut src vers data-consent-src : le navigateur ne charge donc rien
et aucun cookie tiers n'est déposé. Le script consentement.js remplace ces
cadres par un message « Afficher ce contenu » et les active après accord.

Ce traitement côté serveur couvre aussi les vidéos insérées dans les
textes riches, sans avoir à modifier chaque gabarit.
"""
import re

from .models import ConsentementCookies, contenus_externes_acceptes

_RE_IFRAME = re.compile(r"<iframe\b[^>]*>", re.IGNORECASE)
_RE_SRC = re.compile(r"""\ssrc\s*=\s*(["'])(https?:)?//([^/"']+)([^"']*)\1""", re.IGNORECASE)
_PREFIXES_EXCLUS = ("/admin/", "/django-admin/", "/documents/", "/static/", "/media/")


class BlocageContenusTiersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if (
            request.path.startswith(_PREFIXES_EXCLUS)
            or getattr(response, "streaming", False)
            or "text/html" not in response.get("Content-Type", "")
            or contenus_externes_acceptes(request)
        ):
            return response

        try:
            reglages = ConsentementCookies.for_request(request)
        except Exception:
            return response
        if not reglages.actif:
            return response

        contenu = response.content.decode(response.charset or "utf-8", errors="replace")
        if "<iframe" not in contenu.lower():
            return response

        hote_du_site = request.get_host().split(":")[0].lower()

        def bloquer(correspondance):
            balise = correspondance.group(0)
            src = _RE_SRC.search(balise)
            if not src:
                return balise
            domaine = src.group(3).split(":")[0].lower()
            if domaine == hote_du_site:
                return balise
            adresse = f"{src.group(2) or 'https:'}//{src.group(3)}{src.group(4)}"
            remplacement = (
                f' data-consent-src="{adresse}" data-consent-domaine="{domaine}"'
            )
            return balise[: src.start()] + remplacement + balise[src.end():]

        nouveau = _RE_IFRAME.sub(bloquer, contenu)
        if nouveau != contenu:
            response.content = nouveau.encode(response.charset or "utf-8")
            if response.has_header("Content-Length"):
                response["Content-Length"] = str(len(response.content))
        return response
