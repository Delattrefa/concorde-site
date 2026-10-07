"""
Formulaires de l'application 'calendrier'.
"""
from django import forms

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .contrats import AIDE_MISE_EN_FORME, VARIABLES_DISPONIBLES, variables_inconnues
from .models import (
    Activite,
    AnnexeContrat,
    ArticleContrat,
    ContratLocation,
    MiseEnPageContrat,
    Reservation,
    activites_sur,
    jours_occupes,
    occupations_sur,
    reservations_validees_sur,
)


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

        # Plusieurs activités peuvent partager une date, mais pas une date
        # où la salle est louée (réservation validée).
        if debut and fin:
            location = reservations_validees_sur(debut, fin).first()
            if location:
                periode = f"le {location.date_debut:%d/%m/%Y}"
                if location.date_fin != location.date_debut:
                    periode = f"du {location.date_debut:%d/%m/%Y} au {location.date_fin:%d/%m/%Y}"
                raise forms.ValidationError(
                    f"La salle est louée {periode} (réservation de {location.prenom} {location.nom}) : "
                    "impossible d'y ajouter une activité. Choisissez d'autres dates."
                )
        return cleaned_data


class ReservationForm(forms.ModelForm):
    """Formulaire de réservation de salle.

    mode="public" (demande d'un visiteur) : refusée si la salle est déjà
    prise (réservation validée ou activité) sur l'une des dates.
    mode="admin" (administrateur) : jamais refusée ; si la salle est prise,
    la réservation est enregistrée « en attente » (liste d'attente en cas
    d'annulation) et self.mise_en_attente décrit ce qui occupe la salle."""

    mode = "public"

    def __init__(self, *args, mode=None, **kwargs):
        super().__init__(*args, **kwargs)
        if mode:
            self.mode = mode
        self.mise_en_attente = []

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
        if not (debut and fin):
            return cleaned_data

        exclure = self.instance.pk
        if self.mode == "public":
            jours = jours_occupes(debut, fin, exclure_reservation=exclure)
            if jours:
                liste = ", ".join(f"{j:%d/%m/%Y}" for j in jours[:10])
                if len(jours) > 10:
                    liste += "…"
                raise forms.ValidationError(
                    f"La salle n'est pas disponible à ces dates : elle est déjà occupée le {liste}. "
                    "Merci de choisir d'autres dates."
                    if len(jours) == 1 else
                    f"La salle n'est pas disponible à ces dates : elle est déjà occupée les {liste}. "
                    "Merci de choisir d'autres dates."
                )
            return cleaned_data

        # Mode administrateur : mise en attente plutôt que refus.
        statut = cleaned_data.get("statut", self.instance.statut)
        if statut == Reservation.STATUT_VALIDEE:
            occupations = occupations_sur(debut, fin, exclure_reservation=exclure)
            if occupations:
                self.mise_en_attente = occupations
                if "statut" in self.fields:
                    cleaned_data["statut"] = Reservation.STATUT_ATTENTE
                self.instance.statut = Reservation.STATUT_ATTENTE
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

    mode = "admin"


class ReservationTraitementForm(forms.ModelForm):
    """Formulaire technique utilisé côté administration pour changer le
    statut d'une demande (validation / refus)."""

    class Meta:
        model = Reservation
        fields = ["statut"]


NOM_COLLECTION_SIGNATURES = "Signature"


def images_de_signature():
    """Images de la collection « Signature » de la médiathèque Wagtail."""
    from wagtail.images import get_image_model

    return get_image_model().objects.filter(
        collection__name__iexact=NOM_COLLECTION_SIGNATURES
    ).order_by("title")


class ChoixSignatureWidget(forms.RadioSelect):
    """Boutons radio : le gabarit du contrat affiche une vignette par image."""


class ContratLocationForm(forms.ModelForm):
    """Formulaire de rédaction du contrat de location, à partir d'une
    réservation déjà validée. Le locataire et les dates sont déjà connus
    (repris de la réservation) : ce formulaire ne demande que les
    informations propres au contrat lui-même, et la signature (image) du
    délégué à imprimer au-dessus de son nom."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        champ = self.fields["signature"]
        champ.queryset = images_de_signature()
        champ.required = False
        champ.empty_label = "Sans signature (à signer à la main)"
        champ.label = "Signature du délégué"

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
            "signature",
        ]
        widgets = {
            "signature": ChoixSignatureWidget,
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


class SuiviPaiementForm(forms.ModelForm):
    """Une ligne du tableau de suivi des paiements (un contrat de location).
    Les montants ne sont pas modifiables ici : ils proviennent du contrat.
    En cas d'annulation, une ligne supplémentaire permet d'enregistrer la
    date et les remboursements."""

    CHAMPS_ANNULATION = ["date_annulation", "loyer_rembourse", "caution_rendue_annulation", "extrait_annulation"]

    class Meta:
        model = ContratLocation
        fields = [
            "location_payee",
            "caution_payee",
            "caution_remboursee",
            "date_paiement",
            "extrait_paiement",
            "date_remboursement_caution",
            "extrait_remboursement",
            "annule",
            "date_annulation",
            "loyer_rembourse",
            "caution_rendue_annulation",
            "extrait_annulation",
        ]
        widgets = {
            "date_paiement": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}, format=FORMAT_DATE_HTML),
            "date_remboursement_caution": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}, format=FORMAT_DATE_HTML),
            "extrait_paiement": forms.TextInput(attrs={"class": "champ-texte", "placeholder": "N° extrait"}),
            "extrait_remboursement": forms.TextInput(attrs={"class": "champ-texte", "placeholder": "N° extrait"}),
            "annule": forms.CheckboxInput(attrs={"data-annulation-interrupteur": "1"}),
            "date_annulation": forms.DateInput(attrs={"class": "champ-texte", "type": "date"}, format=FORMAT_DATE_HTML),
            "loyer_rembourse": forms.NumberInput(attrs={"class": "champ-texte", "step": "0.01", "min": "0", "placeholder": "0,00"}),
            "caution_rendue_annulation": forms.NumberInput(attrs={"class": "champ-texte", "step": "0.01", "min": "0", "placeholder": "0,00"}),
            "extrait_annulation": forms.TextInput(attrs={"class": "champ-texte", "placeholder": "N° extrait"}),
        }

    def clean(self):
        donnees = super().clean()
        contrat = self.instance

        if donnees.get("caution_remboursee") and not donnees.get("caution_payee"):
            self.add_error(
                "caution_remboursee",
                "Une caution ne peut être remboursée que si elle a été payée.",
            )
        if donnees.get("date_remboursement_caution") and not donnees.get("caution_remboursee"):
            # Une date de remboursement saisie implique le remboursement.
            donnees["caution_remboursee"] = True
            if not donnees.get("caution_payee"):
                self.add_error(
                    "date_remboursement_caution",
                    "Une caution ne peut être remboursée que si elle a été payée.",
                )

        # --- Annulation -----------------------------------------------------
        annule = donnees.get("annule")
        if not annule:
            if any(donnees.get(champ) not in (None, "") for champ in self.CHAMPS_ANNULATION):
                self.add_error("annule", "Cochez « Annulée » pour enregistrer une annulation.")
            # Annulation retirée : la salle doit encore être libre.
            reservation = contrat.reservation
            if contrat.pk and contrat.annule and reservation.statut == Reservation.STATUT_ANNULEE:
                occupations = occupations_sur(
                    reservation.date_debut, reservation.date_fin, exclure_reservation=reservation.pk
                )
                if occupations:
                    self.add_error(
                        "annule",
                        "Impossible de rétablir cette location : la salle est occupée entre-temps ("
                        + " ; ".join(occupations) + ").",
                    )
            return donnees

        if not donnees.get("date_annulation"):
            self.add_error("date_annulation", "Indiquez la date d'annulation.")

        loyer = donnees.get("loyer_rembourse")
        if loyer:
            if not donnees.get("location_payee"):
                self.add_error("loyer_rembourse", "Le loyer n'a pas été payé : il ne peut pas être remboursé.")
            elif loyer > contrat.montant_location:
                self.add_error("loyer_rembourse", f"Supérieur au loyer payé ({contrat.montant_location} €).")

        caution = donnees.get("caution_rendue_annulation")
        if caution:
            if not donnees.get("caution_payee"):
                self.add_error("caution_rendue_annulation", "La caution n'a pas été payée : elle ne peut pas être remboursée.")
            elif caution > contrat.montant_caution:
                self.add_error("caution_rendue_annulation", f"Supérieur à la caution payée ({contrat.montant_caution} €).")
            else:
                # Caution rendue lors de l'annulation : elle n'est plus à rembourser.
                donnees["caution_remboursee"] = True
        return donnees

    def save(self, commit=True):
        contrat = super().save(commit=commit)
        if commit:
            # La réservation suit l'annulation : salle libérée dans le
            # calendrier, ou de nouveau réservée si l'annulation est retirée.
            reservation = contrat.reservation
            if contrat.annule and reservation.statut != Reservation.STATUT_ANNULEE:
                reservation.statut = Reservation.STATUT_ANNULEE
                reservation.save(update_fields=["statut"])
            elif not contrat.annule and reservation.statut == Reservation.STATUT_ANNULEE:
                reservation.statut = Reservation.STATUT_VALIDEE
                reservation.save(update_fields=["statut"])
        return contrat


SuiviPaiementFormSet = forms.modelformset_factory(
    ContratLocation, form=SuiviPaiementForm, extra=0, can_delete=False,
)


class MiseEnPageContratForm(forms.ModelForm):
    """Image de fond de l'en-tête du contrat."""

    supprimer_image = forms.BooleanField(
        label="Retirer l'image d'en-tête actuelle", required=False,
    )

    class Meta:
        model = MiseEnPageContrat
        fields = ["image_entete", "eclaircir_entete"]
        widgets = {
            "image_entete": forms.FileInput(attrs={"accept": "image/jpeg,image/png"}),
        }

    def save(self, commit=True):
        objet = super().save(commit=False)
        if self.cleaned_data.get("supprimer_image") and "image_entete" not in self.changed_data:
            if objet.image_entete:
                objet.image_entete.delete(save=False)
            objet.image_entete = ""
        if commit:
            objet.save()
        return objet
