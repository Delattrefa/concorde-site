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
        from django.db.models.signals import post_delete, post_save
        from wagtail.images import get_image_model

        from .collections import proteger_signature_enregistree
        from .models import Activite, Reservation

        post_save.connect(
            proteger_signature_enregistree, sender=get_image_model(),
            dispatch_uid="calendrier_proteger_signature",
        )

        # Recopie dans l'agenda Google partagé (voir google_agenda.py)
        for modele in (Activite, Reservation):
            post_save.connect(
                _agenda_apres_enregistrement, sender=modele,
                dispatch_uid=f"calendrier_agenda_save_{modele.__name__}",
            )
            post_delete.connect(
                _agenda_apres_suppression, sender=modele,
                dispatch_uid=f"calendrier_agenda_delete_{modele.__name__}",
            )


# L'appel à Google n'a lieu qu'une fois l'enregistrement confirmé en base
# (on_commit) : une erreur ou une annulation ne laisse pas d'événement
# fantôme, et une panne de Google ne fait pas échouer l'enregistrement.

def _agenda_apres_enregistrement(sender, instance, raw=False, update_fields=None, **kwargs):
    from django.db import transaction

    from . import google_agenda

    # raw : import de données (loaddata), rattrapé ensuite par la commande
    # synchroniser_agenda_google
    if raw or (update_fields is not None and set(update_fields) <= {"google_event_id"}):
        return
    transaction.on_commit(lambda: google_agenda.synchroniser(instance))


def _agenda_apres_suppression(sender, instance, **kwargs):
    from django.db import transaction

    from . import google_agenda

    event_id = instance.google_event_id
    if event_id:
        transaction.on_commit(lambda: google_agenda.supprimer(event_id))
