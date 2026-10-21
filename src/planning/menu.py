"""
Sous-menu « Réservations » du menu principal (voir
navigation.context_processors.menus) : le calendrier pour tous, et le
planning des membres pour les personnes connectées.
"""
from django.urls import reverse


def menu_reservations(request):
    """Liens du sous-menu, ou None pour un visiteur (simple lien vers le
    calendrier)."""
    if not request.user.is_authenticated:
        return None
    calendrier, planning = reverse("calendrier:mois_courant"), reverse("planning:accueil")
    return {
        "url": calendrier,
        "actif": request.path.startswith((calendrier, planning)),
        "non_lues": request.user.notifications_planning.filter(lue=False).count(),
        "liens": [
            {"titre": "Calendrier", "url": calendrier, "actif": request.path.startswith(calendrier)},
            {"titre": "Planning", "url": planning, "actif": request.path.startswith(planning)},
        ],
    }
