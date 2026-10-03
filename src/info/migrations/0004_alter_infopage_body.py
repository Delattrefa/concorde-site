import wagtail.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('info', '0003_alter_infopage_body'),
    ]

    operations = [
        migrations.AlterField(
            model_name='infopage',
            name='body',
            field=wagtail.fields.StreamField([('heading', 0), ('paragraph', 1), ('image', 2), ('callout', 5), ('useful_link', 9), ('map', 13)], blank=True, block_lookup={0: ('wagtail.blocks.CharBlock', (), {'form_classname': 'title', 'icon': 'title'}), 1: ('wagtail.blocks.RichTextBlock', (), {'icon': 'pilcrow'}), 2: ('wagtail.images.blocks.ImageChooserBlock', (), {'icon': 'image'}), 3: ('wagtail.blocks.CharBlock', (), {'required': False}), 4: ('wagtail.blocks.RichTextBlock', (), {'required': False}), 5: ('wagtail.blocks.StructBlock', [[('title', 3), ('text', 4)]], {}), 6: ('wagtail.blocks.CharBlock', (), {}), 7: ('wagtail.blocks.PageChooserBlock', (), {'help_text': "Choisissez une page du site (prioritaire sur l'URL ci-dessous).", 'label': 'Page du site', 'required': False}), 8: ('wagtail.blocks.URLBlock', (), {'help_text': "Utilisée seulement si aucune page n'est choisie ci-dessus.", 'label': 'Ou URL externe', 'required': False}), 9: ('wagtail.blocks.StructBlock', [[('title', 6), ('page', 7), ('url', 8)]], {}), 10: ('wagtail.blocks.CharBlock', (), {'label': 'Titre (facultatif)', 'required': False}), 11: ('wagtail.blocks.TextBlock', (), {'help_text': 'Dans Google Maps : Partager > Intégrer une carte > COPIER LE CODE HTML, puis collez ici le code complet (<iframe ...></iframe>). Un lien de partage (maps.app.goo.gl) ne fonctionne pas.', 'label': "Code d'intégration Google Maps", 'rows': 3}), 12: ('wagtail.blocks.IntegerBlock', (), {'default': 400, 'label': 'Hauteur (pixels)', 'max_value': 900, 'min_value': 200}), 13: ('wagtail.blocks.StructBlock', [[('title', 10), ('code', 11), ('height', 12)]], {})}),
        ),
    ]
