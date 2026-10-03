"""
Formulaires de l'application 'calendrier'.
"""
from django import forms

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .contrats import AIDE_MISE_EN_FORME, VARIABLES_DISPONIBLES, variables_inconnues
from .models import Activite, AnnexeContrat, ArticleContrat, ContratLocation, Reservation


# Un champ <input type="date"> n'accepte qu'une valeur au format ISO
# (AAAA-MM-JJ). Sans ce format explicite, Django affiche la date selon
# DATE_INPUT_FORMATS (JJ/MM/AAAA) et le navigateur laisse le champ vide.
FORMAT_DATE_HTML = "%Y-%m-%d"


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
            "date_debut": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}, format=FORMAT_DATE_HTML),
            "date_fin": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}, format=FORMAT_DATE_HTML),
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
            "date_debut": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}, format=FORMAT_DATE_HTML),
            "date_fin": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}, format=FORMAT_DATE_HTML),
            "message": forms.Textarea(attrs={"class": "champ-texte", "rows": 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        debut = cleaned_data.get("date_debut")
        fin = cleaned_data.get("date_fin")
        if debut and fin and fin < debut:
            self.add_error("date_fin", "La date de fin ne peut pas être antérieure à la date de début.")
        return cleaned_data


class ReservationAdminForm(ReservationForm):
    """Réservation encodée directement par un administrateur (demande reçue
    par téléphone, location à un membre...). Même champs que la demande
    publique, plus le statut, validée par défaut."""

    class Meta(ReservationForm.Meta):
        fields = ReservationForm.Meta.fields + ["statut"]
        widgets = {
            **ReservationForm.Meta.widgets,
            "statut": forms.Select(attrs={"class": "champ-texte"}),
        }
        labels = {"date_debut": "Date de début", "date_fin": "Date de fin"}

    def clean(self):
        cleaned_data = super().clean()
        debut = cleaned_data.get("date_debut")
        fin = cleaned_data.get("date_fin")
        statut = cleaned_data.get("statut")

        # Empêche une double location : une réservation validée ne peut pas
        # chevaucher une autre réservation déjà validée.
        if debut and fin and fin >= debut and statut == Reservation.STATUT_VALIDEE:
            conflits = Reservation.objects.filter(
                statut=Reservation.STATUT_VALIDEE,
                date_debut__lte=fin,
                date_fin__gte=debut,
            )
            if self.instance.pk:
                conflits = conflits.exclude(pk=self.instance.pk)
            conflit = conflits.first()
            if conflit:
                raise forms.ValidationError(
                    f"La salle est déjà réservée sur cette période : {conflit}. "
                    "Modifiez les dates, ou enregistrez la réservation « en attente »."
                )
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


class ArticleContratForm(forms.ModelForm):
    """Modification d'un article du contrat-type."""

    class Meta:
        model = ArticleContrat
        fields = ["titre", "texte", "ordre", "actif"]
        widgets = {
            "titre": forms.TextInput(attrs={"class": "champ-texte"}),
            "texte": forms.Textarea(attrs={"class": "champ-texte", "rows": 16}),
            "ordre": forms.NumberInput(attrs={"class": "champ-texte", "min": "0", "step": "1"}),
        }
        help_texts = {"texte": AIDE_MISE_EN_FORME}

    def clean_texte(self):
        texte = self.cleaned_data["texte"]
        inconnues = variables_inconnues(texte)
        if inconnues:
            noms = ", ".join("{%s}" % nom for nom in inconnues)
            disponibles = ", ".join("{%s}" % nom for nom in VARIABLES_DISPONIBLES)
            raise forms.ValidationError(
                f"Variable(s) inconnue(s) : {noms}. Variables disponibles : {disponibles}."
            )
        return texte


class AnnexeContratForm(forms.ModelForm):
    """Ajout ou remplacement d'une annexe PDF du contrat-type."""

    class Meta:
        model = AnnexeContrat
        fields = ["titre", "fichier", "ordre", "actif"]
        widgets = {
            "titre": forms.TextInput(attrs={"class": "champ-texte"}),
            "fichier": forms.ClearableFileInput(attrs={"accept": "application/pdf,.pdf"}),
            "ordre": forms.NumberInput(attrs={"class": "champ-texte", "min": "0", "step": "1"}),
        }

    def clean_fichier(self):
        fichier = self.cleaned_data.get("fichier")
        # Nouveau fichier envoyé : vérifier que c'est un PDF lisible, pour
        # ne pas bloquer ensuite la génération des contrats.
        if fichier and hasattr(fichier, "content_type"):
            try:
                fichier.seek(0)
                nb_pages = len(PdfReader(fichier).pages)
            except (PdfReadError, ValueError, OSError):
                raise forms.ValidationError("Ce fichier n'est pas un PDF valide.")
            finally:
                fichier.seek(0)
            if nb_pages == 0:
                raise forms.ValidationError("Ce PDF ne contient aucune page.")
        return fichier
