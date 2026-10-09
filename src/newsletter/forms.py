import re

from django import forms
from django.core.validators import EmailValidator

# Contrôle plus strict que la validation standard : domaine avec au moins un
# point et une extension alphabétique (refuse « nom@site », « nom@site.1 »...).
_RE_EMAIL_STRICT = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24}$"
)


def valider_email_strict(valeur):
    EmailValidator(message="Adresse e-mail invalide.")(valeur)
    local = valeur.split("@", 1)[0]
    if (
        not _RE_EMAIL_STRICT.match(valeur)
        or ".." in valeur
        or local.startswith(".")
        or local.endswith(".")
        or len(valeur) > 254
    ):
        raise forms.ValidationError("Adresse e-mail invalide. Exemple : prenom.nom@exemple.be")


class InscriptionForm(forms.Form):
    email = forms.CharField(
        label="Adresse e-mail",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "prenom.nom@exemple.be", "required": True}),
    )
    prenom = forms.CharField(
        label="Prénom (facultatif)", max_length=100, required=False,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    nom = forms.CharField(
        label="Nom (facultatif)", max_length=100, required=False,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    consentement = forms.BooleanField(
        label="J'accepte de recevoir la newsletter.",
        error_messages={"required": "Merci de cocher la case pour confirmer votre inscription."},
    )
    # Piège à robots : champ invisible pour les humains, rempli par les robots.
    site_web = forms.CharField(required=False, widget=forms.TextInput(attrs={
        "tabindex": "-1", "autocomplete": "off", "class": "newsletter-form__piege", "aria-hidden": "true",
    }))

    def __init__(self, *args, texte_consentement=None, **kwargs):
        super().__init__(*args, **kwargs)
        if texte_consentement:
            self.fields["consentement"].label = texte_consentement

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        valider_email_strict(email)
        return email

    def clean_prenom(self):
        return " ".join((self.cleaned_data.get("prenom") or "").split())

    def clean_nom(self):
        return " ".join((self.cleaned_data.get("nom") or "").split())

    @property
    def est_un_robot(self):
        return bool(self.data.get("site_web"))
