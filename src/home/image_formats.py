"""
Formats proposés lors de l'insertion d'une image dans un champ de texte
riche (texte des sections, pages Info, actualités...). Wagtail charge
automatiquement ce fichier (image_formats.py) au démarrage.

Les formats d'origine de Wagtail (pleine largeur, gauche, droite) restent
disponibles pour le contenu existant. Les styles correspondants sont dans
static/css/images.css.
"""
from wagtail.images.formats import Format, register_image_format

register_image_format(Format(
    "petite-gauche", "Petite, à gauche du texte",
    "richtext-image richtext-image--petite richtext-image--gauche", "width-500",
))
register_image_format(Format(
    "petite-droite", "Petite, à droite du texte",
    "richtext-image richtext-image--petite richtext-image--droite", "width-500",
))
register_image_format(Format(
    "moyenne", "Moyenne, centrée",
    "richtext-image richtext-image--moyenne", "width-900",
))
register_image_format(Format(
    "grande", "Grande, toute la largeur",
    "richtext-image richtext-image--grande", "width-1600",
))
