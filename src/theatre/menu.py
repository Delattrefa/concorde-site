"""
Liens de l'application théâtre, affichés dans le sous-menu « Théâtre » du
menu principal du site (voir navigation.context_processors.menus).

Pour ajouter une page de l'application au menu, il suffit d'ajouter une
entrée ici : (libellé, nom d'URL, icône Bootstrap Icons).
"""
from django.urls import reverse

LIENS = [
    ("Représentations", "representation_list", "bi-calendar-event"),
    ("Réservations", "reservation_list", "bi-ticket-perforated"),
]


def menu_theatre(request):
    """Liens du sous-menu Théâtre, ou None si l'utilisateur n'a pas accès
    à l'application."""
    if not request.user.has_perm("theatre.acces_application"):
        return None
    nom_url_courant = getattr(request.resolver_match, "url_name", None)
    accueil = reverse("representation_list")
    return {
        "url": accueil,
        "actif": request.path.startswith(accueil),
        "liens": [
            {
                "titre": titre,
                "url": reverse(nom_url),
                "icone": icone,
                "actif": nom_url == nom_url_courant,
            }
            for titre, nom_url, icone in LIENS
        ],
    }
