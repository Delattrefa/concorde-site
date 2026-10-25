from django import template

from planning.models import nom_membre as _nom_membre

register = template.Library()

# Onglet du planning correspondant à chaque page (nom d'URL)
ONGLETS = {
    "plannings": "plannings",
    "couverture": "couverture",
    "invitations": "invitations",
    "disponibilites": "disponibilites",
    "sondages": "sondages", "sondage": "sondages", "sondage_nouveau": "sondages",
    "canaux": "discussions", "canal": "discussions", "canal_nouveau": "discussions",
    "notifications": "notifications",
}


@register.filter
def nom_membre(user):
    return _nom_membre(user)


@register.simple_tag(takes_context=True)
def onglet_actif(context):
    match = getattr(context.get("request"), "resolver_match", None)
    return ONGLETS.get(getattr(match, "url_name", ""), "agenda")


@register.inclusion_tag("planning/_jauge.html")
def jauge(inscrits, besoin):
    taux = round(min(inscrits, besoin) * 100 / besoin) if besoin else 100
    etat = "ok" if inscrits >= besoin else ("vide" if inscrits == 0 else "partiel")
    return {"inscrits": inscrits, "besoin": besoin, "taux": taux, "etat": etat}
