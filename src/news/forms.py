"""
Formulaires de l'éditeur d'actualités du site : création et modification
complètes d'une actualité sans passer par l'admin Wagtail.

Il s'agit volontairement d'un formulaire Django simple (forms.Form) et non
d'un ModelForm : NewsPage est une page Wagtail (arborescence de pages), sa
création réelle se fait dans la vue via NewsIndexPage.add_child() plutôt
que via un simple form.save().

Le contenu de l'article (texte enrichi, intertitres, images positionnées,
citations…) est composé dans le navigateur par l'éditeur par blocs
(static/news/js/editeur.js) et envoyé en JSON dans le champ caché « corps »,
converti par news/editeur.py.
"""
from django import forms
from django.utils import timezone

from media_gallery.forms import TAILLE_MAX_PHOTO

FORMATS_PHOTO = "image/jpeg,image/png,image/webp,image/gif"


class ChampPhoto(forms.ImageField):
    """Image valide (vérifiée avec Pillow) de 20 Mo au maximum."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", forms.ClearableFileInput(attrs={"accept": FORMATS_PHOTO}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if data and getattr(data, "size", 0) > TAILLE_MAX_PHOTO:
            raise forms.ValidationError(f"« {data.name} » dépasse 20 Mo.")
        return super().clean(data, initial)


class NewsPageForm(forms.Form):
    """Champs d'une actualité, les mêmes que dans l'admin Wagtail."""

    titre = forms.CharField(
        label="Titre",
        max_length=255,
        widget=forms.TextInput(attrs={"class": "champ-texte"}),
    )
    date = forms.DateField(
        label="Date de publication",
        help_text="Sert à trier les actualités (la plus récente en premier).",
        widget=forms.DateInput(attrs={"type": "date", "class": "champ-texte"}, format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d", "%d/%m/%Y"],
    )
    auteur = forms.CharField(
        label="Auteur",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "champ-texte"}),
    )
    intro = forms.CharField(
        label="Résumé court (affiché dans la liste des actualités)",
        max_length=300,
        required=False,
        widget=forms.Textarea(attrs={"class": "champ-texte", "rows": 2}),
    )
    a_la_une = forms.BooleanField(
        label="À la une",
        required=False,
        help_text=(
            "Affiche cette actualité sur la page d'accueil à la place de la plus "
            "récente, quelle que soit sa date."
        ),
    )
    image = ChampPhoto(
        label="Image mise en avant (facultatif)",
        required=False,
        help_text="Grande image en haut de l'article et vignette dans la liste des actualités.",
    )
    retirer_image = forms.BooleanField(label="Retirer l'image mise en avant", required=False)
    corps = forms.CharField(required=False, widget=forms.HiddenInput)
    mots_cles = forms.CharField(
        label="Mots-clés (facultatif)",
        required=False,
        help_text="Séparés par des virgules, ex : théâtre, Blé qui Lève. Permettent de filtrer les actualités.",
        widget=forms.TextInput(attrs={"class": "champ-texte"}),
    )
    lien_texte = forms.CharField(
        label="Texte du lien (facultatif)",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "champ-texte", "placeholder": "Ex : Réserver vos places"}),
    )
    lien_url = forms.URLField(
        label="Adresse du lien (facultatif)",
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"class": "champ-texte", "placeholder": "https://..."}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].initial = timezone.localdate

    def clean_mots_cles(self):
        mots = [m.strip() for m in self.cleaned_data["mots_cles"].split(",")]
        # Sans doublon (sans tenir compte des majuscules), dans l'ordre saisi
        vus, resultat = set(), []
        for mot in mots:
            if mot and mot.lower() not in vus:
                vus.add(mot.lower())
                resultat.append(mot[:100])
        return resultat

    def clean(self):
        """Un texte de lien sans adresse (ou l'inverse) n'a pas de sens :
        on impose la cohérence des deux champs."""
        cleaned_data = super().clean()
        texte = cleaned_data.get("lien_texte")
        url = cleaned_data.get("lien_url")

        if texte and not url:
            self.add_error("lien_url", "Veuillez indiquer l'adresse du lien correspondant.")
        elif url and not texte:
            # Valeur par défaut raisonnable si seule l'adresse a été saisie.
            cleaned_data["lien_texte"] = "En savoir plus"

        return cleaned_data


class PhotoArticleForm(forms.Form):
    """Envoi d'une photo pour un bloc image de l'éditeur (requête JavaScript)."""

    photo = ChampPhoto()
