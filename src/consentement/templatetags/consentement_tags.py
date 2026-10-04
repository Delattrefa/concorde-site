from django import template

from ..models import NOM_COOKIE, VERSION_COOKIE, ConsentementCookies

register = template.Library()


@register.inclusion_tag("consentement/banniere.html", takes_context=True)
def banniere_consentement(context):
    """Bandeau de consentement (affiché par consentement.js si aucun choix
    n'a encore été fait) et fenêtre de personnalisation."""
    request = context.get("request")
    reglages = ConsentementCookies.for_request(request) if request else None
    return {
        "request": request,
        "reglages": reglages,
        "nom_cookie": NOM_COOKIE,
        "version_cookie": VERSION_COOKIE,
    }
