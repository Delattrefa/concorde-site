from django.core.exceptions import ValidationError
from django.db import models

from modelcluster.fields import ParentalKey

from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.fields import RichTextField
from wagtailseo.models import SeoMixin

from info.models import extraire_url_google_maps


class ContactFormField(AbstractFormField):
    page = ParentalKey(
        "contact.ContactPage", on_delete=models.CASCADE, related_name="form_fields"
    )


class ContactPage(SeoMixin, AbstractEmailForm):
    """Page 'Contactez-nous' : formulaire Wagtail classique (nom, e-mail,
    message…) + coordonnées et carte, avec envoi d'e-mail automatique."""

    max_count = 1

    intro = RichTextField(blank=True)
    thank_you_text = RichTextField(
        blank=True, default="<p>Merci pour votre message, nous reviendrons vers vous rapidement !</p>"
    )

    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email_display = models.EmailField(blank=True)
    map_embed_url = models.TextField(
        "Carte Google Maps",
        blank=True,
        help_text=(
            "Dans Google Maps : Partager > Intégrer une carte > COPIER LE CODE HTML, "
            "puis collez ici le code complet (<iframe ...></iframe>). "
            "Un lien de partage (maps.app.goo.gl) ne fonctionne pas."
        ),
    )

    content_panels = AbstractEmailForm.content_panels + [
        FieldPanel("intro"),
        InlinePanel("form_fields", label="Champs du formulaire"),
        FieldPanel("thank_you_text"),
        MultiFieldPanel(
            [
                FieldPanel("address"),
                FieldPanel("phone"),
                FieldPanel("email_display"),
                FieldPanel("map_embed_url"),
            ],
            heading="Coordonnées",
        ),
        MultiFieldPanel(
            [
                FieldRowPanel(
                    [
                        FieldPanel("from_address"),
                        FieldPanel("to_address"),
                    ]
                ),
                FieldPanel("subject"),
            ],
            "Notification par e-mail",
        ),
    ]

    promote_panels = SeoMixin.seo_panels

    def clean(self):
        """Accepte le code <iframe> complet fourni par Google Maps (ou sa
        seule adresse) et n'en conserve que l'adresse de la carte."""
        super().clean()
        if self.map_embed_url:
            url = extraire_url_google_maps(self.map_embed_url)
            if not url:
                raise ValidationError({
                    "map_embed_url": (
                        "Code non reconnu. Collez le code HTML fourni par Google Maps dans "
                        "Partager > Intégrer une carte (il commence par "
                        "<iframe src=\"https://www.google.com/maps/embed...)."
                    ),
                })
            self.map_embed_url = url

    class Meta:
        verbose_name = "Page de contact"
