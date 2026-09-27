"""
Formulaire permettant à un utilisateur connecté d'ajouter directement une
actualité depuis le site, sans passer par l'admin Wagtail.

Il s'agit volontairement d'un formulaire Django simple (forms.Form) et non
d'un ModelForm : NewsPage est une page Wagtail (arborescence de pages), sa
création réelle se fait dans la vue via NewsIndexPage.add_child() plutôt
que via un simple form.save().
"""
from django import forms


class NewsPageForm(forms.Form):
    """Champs proposés à l'utilisateur pour publier rapidement une actualité."""

    titre = forms.CharField(
        label="Titre",
        max_length=255,
        widget=forms.TextInput(attrs={"class": "champ-texte"}),
    )
    intro = forms.CharField(
        label="Résumé court (affiché dans la liste des actualités)",
        max_length=300,
        required=False,
        widget=forms.Textarea(attrs={"class": "champ-texte", "rows": 2}),
    )
    contenu = forms.CharField(
        label="Contenu de l'article",
        required=False,
        widget=forms.Textarea(attrs={"class": "champ-texte", "rows": 8}),
    )
    image = forms.ImageField(
        label="Image mise en avant (facultatif)",
        required=False,
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
        widget=forms.URLInput(attrs={"class": "champ-texte", "placeholder": "https://..."}),
    )

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
