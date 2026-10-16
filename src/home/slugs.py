"""
Slugs sans accents.

Les serveurs d'o2switch ne servent pas les URL contenant des caractères
accentués : tous les slugs sont donc translittérés en ASCII
(« Marché de Noël » → « marche-de-noel »).
"""

from django import forms
from django.db import models
from django.utils.text import slugify
from wagtail.admin.forms.models import register_form_field_override
from wagtail.admin.widgets import SlugInput

# Ligatures que la décomposition Unicode ne sait pas séparer
LIGATURES = str.maketrans({"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE", "ß": "ss"})


def slug_ascii(valeur):
    """Slug ASCII : accents retirés, ligatures développées."""
    return slugify(str(valeur).translate(LIGATURES))


class SlugAsciiField(forms.SlugField):
    """Champ de slug de l'administration : convertit au lieu de refuser."""

    def to_python(self, value):
        value = super().to_python(value)
        return slug_ascii(value) if value else value


def activer():
    """Utilise SlugAsciiField pour tous les slugs de l'administration Wagtail."""
    register_form_field_override(
        models.SlugField,
        override={"form_class": SlugAsciiField, "widget": SlugInput},
    )
