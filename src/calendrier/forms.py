"""
Formulaires de l'application 'calendrier'.
"""
from django import forms

from .models import Activite, ContratLocation, Reservation


class ActiviteForm(forms.ModelForm):
    """Formulaire d'ajout / modification d'une activité.
    Réservé aux utilisateurs connectés (voir vues avec LoginRequiredMixin)."""

    class Meta:
        model = Activite
        fields = [
            "nom",
            "description",
            "date_debut",
            "date_fin",
            "visibilite",
            "couleur",
        ]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "champ-texte", "placeholder": "Ex : Répétition théâtre"}),
            "description": forms.Textarea(attrs={"class": "champ-texte", "rows": 4}),
            "date_debut": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}),
            "date_fin": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}),
            "visibilite": forms.RadioSelect,
            "couleur": forms.TextInput(attrs={"class": "champ-texte", "type": "color"}),
        }
        labels = {
            "couleur": "Couleur (facultatif)",
        }

    def clean(self):
        """Validation croisée des dates (redondante avec Model.clean, mais
        permet d'afficher l'erreur directement sous le bon champ du
        formulaire plutôt qu'en erreur générale)."""
        cleaned_data = super().clean()
        debut = cleaned_data.get("date_debut")
        fin = cleaned_data.get("date_fin")
        if debut and fin and fin < debut:
            self.add_error("date_fin", "La date de fin ne peut pas être antérieure à la date de début.")
        return cleaned_data


class ReservationForm(forms.ModelForm):
    """Formulaire public de demande de réservation de salle.
    Accessible sans connexion."""

    class Meta:
        model = Reservation
        fields = [
            "nom",
            "prenom",
            "adresse",
            "email",
            "telephone",
            "date_debut",
            "date_fin",
            "message",
        ]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "champ-texte"}),
            "prenom": forms.TextInput(attrs={"class": "champ-texte"}),
            "adresse": forms.TextInput(attrs={"class": "champ-texte"}),
            "email": forms.EmailInput(attrs={"class": "champ-texte", "placeholder": "Ex : nom@exemple.be"}),
            "telephone": forms.TextInput(attrs={"class": "champ-texte", "placeholder": "Ex : 0470 12 34 56"}),
            "date_debut": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}),
            "date_fin": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}),
            "message": forms.Textarea(attrs={"class": "champ-texte", "rows": 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        debut = cleaned_data.get("date_debut")
        fin = cleaned_data.get("date_fin")
        if debut and fin and fin < debut:
            self.add_error("date_fin", "La date de fin ne peut pas être antérieure à la date de début.")
        return cleaned_data


class ReservationTraitementForm(forms.ModelForm):
    """Formulaire technique utilisé côté administration pour changer le
    statut d'une demande (validation / refus)."""

    class Meta:
        model = Reservation
        fields = ["statut"]


class ContratLocationForm(forms.ModelForm):
    """Formulaire de rédaction du contrat de location, à partir d'une
    réservation déjà validée. Le locataire et les dates sont déjà connus
    (repris de la réservation) : ce formulaire ne demande que les
    informations propres au contrat lui-même."""

    class Meta:
        model = ContratLocation
        fields = [
            "delegue_prenom",
            "delegue_nom",
            "local_salle",
            "local_cafe",
            "local_cuisine",
            "local_toilettes",
            "montant_location",
            "montant_caution",
        ]
        widgets = {
            "delegue_prenom": forms.TextInput(attrs={"class": "champ-texte"}),
            "delegue_nom": forms.TextInput(attrs={"class": "champ-texte"}),
            "montant_location": forms.NumberInput(attrs={"class": "champ-texte", "step": "0.01", "min": "0"}),
            "montant_caution": forms.NumberInput(attrs={"class": "champ-texte", "step": "0.01", "min": "0"}),
        }
        labels = {
            "montant_location": "Montant de la location (€)",
            "montant_caution": "Montant de la caution (€)",
        }
