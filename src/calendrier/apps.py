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

    def ready(self):
        from django.db.models.signals import post_save
        from wagtail.images import get_image_model

        from .collections import proteger_signature_enregistree

        post_save.connect(
            proteger_signature_enregistree, sender=get_image_model(),
            dispatch_uid="calendrier_proteger_signature",
        )
