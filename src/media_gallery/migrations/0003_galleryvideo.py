import django.db.models.deletion
import modelcluster.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("media_gallery", "0002_galleryalbum_canonical_url_galleryalbum_og_image_and_more"),
        ("wagtailimages", "0027_image_description"),
    ]

    operations = [
        migrations.AlterField(
            model_name="galleryalbum",
            name="cover_image",
            field=models.ForeignKey(
                blank=True, help_text="Photo de couverture affichée dans la liste des albums (sinon la première photo).",
                null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="wagtailimages.image",
            ),
        ),
        migrations.CreateModel(
            name="GalleryVideo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sort_order", models.IntegerField(blank=True, editable=False, null=True)),
                ("url", models.URLField(help_text="Copiez l'adresse de la vidéo (barre d'adresse ou bouton « Partager ») : YouTube, Vimeo, Facebook, Dailymotion, Instagram, TikTok.", max_length=500, verbose_name="Lien de la vidéo")),
                ("titre", models.CharField(blank=True, max_length=255, verbose_name="Titre")),
                ("page", modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name="videos", to="media_gallery.galleryalbum")),
                ("vignette", models.ForeignKey(blank=True, help_text="Image d'aperçu affichée dans l'album. Sans image, une vignette aux couleurs du site est utilisée.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="wagtailimages.image", verbose_name="Vignette (facultatif)")),
            ],
            options={
                "verbose_name": "Vidéo",
                "verbose_name_plural": "Vidéos",
                "ordering": ["sort_order"],
                "abstract": False,
            },
        ),
    ]
