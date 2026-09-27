from django.apps import AppConfig


class CalendrierConfig(AppConfig):
    """Configuration de l'application 'calendrier'.

    Cette application gère :
    - le calendrier mensuel des activités de l'ASBL,
    - les demandes de réservation de salle faites par le public,
    - la validation ou le refus de ces demandes par un administrateur.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "calendrier"
    verbose_name = "Calendrier & réservations de salle"
