from django.db import models

from modelcluster.fields import ParentalKey

from wagtail.admin.panels import FieldPanel, FieldRowPanel, InlinePanel, MultiFieldPanel
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.fields import RichTextField
from wagtailseo.models import SeoMixin


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
    map_embed_url = models.URLField(
        blank=True,
        help_text="URL d'intégration Google Maps (menu Partager > Intégrer une carte).",
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

    class Meta:
        verbose_name = "Page de contact"
