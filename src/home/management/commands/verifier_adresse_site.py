"""
Vérifie l'adresse du site déclarée dans Wagtail (Paramètres › Sites).

Wagtail s'en sert pour toutes les adresses complètes : liens des boutons de
partage, aperçus Facebook/WhatsApp (balises og:url, og:image), adresse
canonique, liens des e-mails. Restée à « localhost » (valeur créée par
Wagtail, ou importée d'une base locale), elle rend ces liens inutilisables.

La commande avertit sans rien modifier et sans faire échouer le
déploiement.

Usage : python manage.py verifier_adresse_site
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from wagtail.models import Site

HOTES_LOCAUX = {"localhost", "127.0.0.1", "::1"}


def problemes_adresse_site():
    """Liste des problèmes trouvés (vide si tout va bien)."""
    hotes_autorises = set(settings.ALLOWED_HOSTS)
    problemes = []
    for site in Site.objects.all():
        nom = f"« {site.site_name or site.hostname} »"
        if site.hostname in HOTES_LOCAUX:
            problemes.append(f"Le site {nom} a pour nom d'hôte « {site.hostname} ».")
        elif "*" not in hotes_autorises and site.hostname not in hotes_autorises:
            problemes.append(
                f"Le nom d'hôte « {site.hostname} » du site {nom} n'est pas dans "
                f"ALLOWED_HOSTS ({', '.join(sorted(hotes_autorises)) or 'vide'})."
            )
        if site.port != 443:
            problemes.append(f"Le site {nom} utilise le port {site.port} : ses liens ne sont pas en https.")
    return problemes


class Command(BaseCommand):
    help = "Avertit si l'adresse du site dans Wagtail est incorrecte (localhost, port…)."

    def handle(self, *args, **options):
        problemes = problemes_adresse_site()
        if not problemes:
            self.stdout.write("Adresse du site correcte.")
            return
        self.stderr.write(self.style.WARNING("⚠ Adresse du site à corriger :"))
        for probleme in problemes:
            self.stderr.write(f"  - {probleme}")
        self.stderr.write(
            "  Les liens de partage et les aperçus Facebook/WhatsApp sont faux tant que ce "
            "n'est pas corrigé. Admin Wagtail → Paramètres → Sites : nom d'hôte "
            "www.la-concorde.be, port 443."
        )
