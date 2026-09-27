from .models import FooterMenu, MainMenu


def menus(request):
    """Rend le menu principal et les liens du pied de page disponibles
    dans tous les templates, sans avoir à les repasser depuis chaque vue."""
    return {
        "main_menu": MainMenu.objects.prefetch_related("items").first(),
        "footer_menu": FooterMenu.objects.prefetch_related("links").first(),
    }
