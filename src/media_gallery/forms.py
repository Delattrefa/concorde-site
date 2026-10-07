"""
Formulaire d'ajout de plusieurs photos en une seule fois dans un album.

Django gère nativement un champ de formulaire par fichier unique : pour
accepter plusieurs fichiers sélectionnés en une fois (attribut HTML
`multiple` sur le champ de saisie), il faut un champ et un widget dédiés,
qui interceptent la liste de fichiers reçue plutôt qu'un fichier unique.
"""
from django import forms


class MultipleFileInput(forms.ClearableFileInput):
    """Widget de saisie de fichier acceptant plusieurs fichiers à la fois."""

    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        # Par défaut, un widget de fichier ne récupère qu'un seul fichier
        # (files.get) : on récupère ici la liste complète des fichiers
        # sélectionnés (files.getlist).
        upload = files.getlist(name)
        if not upload:
            return None
        return upload


class MultipleFileField(forms.FileField):
    """Champ de formulaire associé, qui valide chaque fichier de la liste
    individuellement (et non un seul fichier comme forms.FileField)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        valider_un_fichier = super().clean
        if isinstance(data, (list, tuple)):
            return [valider_un_fichier(fichier, initial) for fichier in data]
        return valider_un_fichier(data, initial)


class AjoutPhotosForm(forms.Form):
    """Formulaire d'ajout de plusieurs photos à un album existant."""

    images = MultipleFileField(
        label="Photos à ajouter",
        help_text="Vous pouvez sélectionner plusieurs fichiers à la fois (Ctrl/Cmd + clic, ou glisser-déposer).",
    )


class AjoutVideoForm(forms.Form):
    """Ajout rapide d'une vidéo (lien YouTube, Facebook...) à un album."""

    url = forms.URLField(
        label="Lien de la vidéo",
        max_length=500,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"placeholder": "https://www.youtube.com/watch?v=…"}),
    )
    titre = forms.CharField(label="Titre (facultatif)", max_length=255, required=False)

    def clean_url(self):
        from .videos import PLATEFORMES, analyser_video

        url = self.cleaned_data["url"]
        if not analyser_video(url):
            raise forms.ValidationError(
                "Lien non reconnu. Plateformes acceptées : " + ", ".join(PLATEFORMES)
                + ". Utilisez l'adresse de la vidéo elle-même."
            )
        return url
