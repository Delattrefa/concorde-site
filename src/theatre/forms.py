from django import forms
from .models import Representation, Reservation, POSITION_RANGEE, POSITION_COTE, RANGEE_PREFEREE_CHOICES


class RepresentationForm(forms.ModelForm):
    """Formulaire de création/modification d'une représentation."""

    class Meta:
        model = Representation
        fields = ['nom', 'date', 'prix_adulte', 'prix_enfant']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom du spectacle'}),
            'date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d'
            ),
            'prix_adulte': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'prix_enfant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
        labels = {
            'nom': 'Nom de la représentation',
            'date': 'Date',
            'prix_adulte': 'Prix adulte (€)',
            'prix_enfant': 'Prix enfant (€)',
        }


class ReservationForm(forms.ModelForm):
    """Formulaire de création/modification d'une réservation."""

    class Meta:
        model = Reservation
        fields = [
            'representation', 'nom', 'prenom',
            'nb_adultes', 'nb_enfants',
            'preference_rangee', 'preference_cote',
            'rangee_preferee','remarque'
        ]
        widgets = {
            'representation': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'}),
            'nb_adultes': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'value': '0'}),
            'nb_enfants': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'value': '0'}),
            'preference_rangee': forms.Select(attrs={'class': 'form-select'},choices=POSITION_RANGEE),
            'preference_cote': forms.Select(attrs={'class': 'form-select'},choices=POSITION_COTE),
            'rangee_preferee': forms.Select(attrs={'class': 'form-select'},choices=RANGEE_PREFEREE_CHOICES),
            'remarque': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Remarque éventuelle...'}),
        }

    def clean(self):
        """Validation : au moins une place doit être réservée."""
        cleaned_data = super().clean()
        nb_adultes = cleaned_data.get('nb_adultes', 0)
        nb_enfants = cleaned_data.get('nb_enfants', 0)
        if nb_adultes + nb_enfants == 0:
            raise forms.ValidationError("Veuillez indiquer au moins une place (adulte ou enfant).")
        return cleaned_data


class ReservationEditForm(ReservationForm):
    """Formulaire d'édition avec tous les champs modifiables."""
    pass