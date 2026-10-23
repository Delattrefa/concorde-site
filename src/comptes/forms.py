from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

from .models import InvitationMembre


def email_deja_utilise(email):
    return get_user_model().objects.filter(email__iexact=email).exists()


class InscriptionForm(forms.Form):
    prenom = forms.CharField(label="Prénom", max_length=150)
    nom = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="Adresse e-mail")
    mot_de_passe = forms.CharField(
        label="Mot de passe", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    confirmation = forms.CharField(
        label="Confirmez le mot de passe", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if email_deja_utilise(email):
            raise ValidationError("Cette adresse est déjà utilisée par un compte. Connectez-vous avec celui-ci.")
        return email

    def clean(self):
        donnees = super().clean()
        mot_de_passe, confirmation = donnees.get("mot_de_passe"), donnees.get("confirmation")
        if mot_de_passe and confirmation and mot_de_passe != confirmation:
            self.add_error("confirmation", "Les deux mots de passe ne sont pas identiques.")
        elif mot_de_passe:
            # Règles du site (10 caractères, pas trop courant, pas proche du nom…)
            provisoire = get_user_model()(first_name=donnees.get("prenom", ""), last_name=donnees.get("nom", ""),
                                          email=donnees.get("email", ""), username=donnees.get("email", ""))
            try:
                password_validation.validate_password(mot_de_passe, provisoire)
            except ValidationError as erreur:
                self.add_error("mot_de_passe", erreur)
        return donnees


class InvitationAdminForm(forms.ModelForm):
    class Meta:
        model = InvitationMembre
        fields = ["email", "prenom", "nom", "message"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if email_deja_utilise(email):
            raise ValidationError("Un compte existe déjà avec cette adresse.")
        en_attente = [i for i in InvitationMembre.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
                      if i.utilisable()]
        if en_attente:
            raise ValidationError("Une invitation est déjà en attente pour cette adresse : "
                                  "utilisez l'action « Renvoyer l'invitation » dans la liste.")
        return email
