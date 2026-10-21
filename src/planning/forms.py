from django import forms
from django.contrib.auth.models import Group

from .models import Canal, Creneau, Disponibilite, Evenement, Preferences, Sondage, nom_membre
from .services import REPETITIONS, membres_actifs

FORMAT_DATETIME = "%Y-%m-%dT%H:%M"


class ChampDateHeure(forms.DateTimeField):
    widget = forms.DateTimeInput(attrs={"type": "datetime-local"}, format=FORMAT_DATETIME)

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("input_formats", [FORMAT_DATETIME, "%Y-%m-%d %H:%M"])
        super().__init__(*args, **kwargs)


class ChoixMembres(forms.ModelMultipleChoiceField):
    widget = forms.CheckboxSelectMultiple

    def __init__(self, label="Membres", **kwargs):
        super().__init__(queryset=membres_actifs(), required=False, label=label, **kwargs)

    def label_from_instance(self, membre):
        return nom_membre(membre)


class ChoixGroupes(forms.ModelMultipleChoiceField):
    widget = forms.CheckboxSelectMultiple

    def __init__(self, label="Groupes", **kwargs):
        super().__init__(queryset=Group.objects.order_by("name"), required=False, label=label, **kwargs)


def membres_choisis(cleaned_data, champ_membres, champ_groupes):
    """Membres cochés + membres des groupes cochés."""
    ids = {m.pk for m in cleaned_data.get(champ_membres) or []}
    for groupe in cleaned_data.get(champ_groupes) or []:
        ids |= set(groupe.user_set.filter(is_active=True).values_list("pk", flat=True))
    return ids


class EvenementForm(forms.ModelForm):
    debut = ChampDateHeure(label="Début")
    fin = ChampDateHeure(label="Fin")
    repetition = forms.ChoiceField(label="Répétition", choices=REPETITIONS, required=False)
    repeter_jusquau = forms.DateField(label="Jusqu'au", required=False,
                                      widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    inviter_membres = ChoixMembres(label="Inviter des membres")
    inviter_groupes = ChoixGroupes(label="Inviter des groupes")
    duree_creneaux = forms.IntegerField(
        label="Découper en créneaux de (minutes)", required=False, min_value=15, max_value=24 * 60,
        help_text="Facultatif : ex. 120 pour des créneaux de 2 heures (tenue d'un stand, ménage…).",
    )
    besoin_creneaux = forms.IntegerField(label="Bénévoles par créneau", required=False, min_value=1,
                                         max_value=99, initial=1)
    appliquer_serie = forms.BooleanField(
        label="Appliquer aussi aux occurrences suivantes de la série", required=False,
        help_text="Titre, description, lieu, type et horaires ; chaque occurrence garde sa date.",
    )

    class Meta:
        model = Evenement
        fields = ["type", "titre", "description", "lieu", "debut", "fin", "reserve_aux_invites"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            for champ in ("repetition", "repeter_jusquau", "duree_creneaux", "besoin_creneaux"):
                del self.fields[champ]
            if not self.instance.serie:
                del self.fields["appliquer_serie"]
        else:
            del self.fields["appliquer_serie"]

    def clean(self):
        donnees = super().clean()
        debut, fin = donnees.get("debut"), donnees.get("fin")
        if debut and fin and fin <= debut:
            self.add_error("fin", "La fin doit être après le début.")
        if donnees.get("repetition"):
            jusquau = donnees.get("repeter_jusquau")
            if not jusquau:
                self.add_error("repeter_jusquau", "Indiquez jusqu'à quand répéter.")
            elif debut and jusquau <= debut.date():
                self.add_error("repeter_jusquau", "Cette date doit suivre le début.")
        return donnees

    def invites(self):
        return membres_choisis(self.cleaned_data, "inviter_membres", "inviter_groupes")


class InviterForm(forms.Form):
    membres = ChoixMembres()
    groupes = ChoixGroupes()

    def invites(self):
        return membres_choisis(self.cleaned_data, "membres", "groupes")


class DecouperForm(forms.Form):
    duree = forms.IntegerField(label="Durée d'un créneau (minutes)", min_value=15, max_value=24 * 60, initial=120)
    besoin = forms.IntegerField(label="Bénévoles par créneau", min_value=1, max_value=99, initial=2)
    libelle = forms.CharField(label="Poste (facultatif)", max_length=100, required=False,
                              help_text="Ex. : bar. Découpez plusieurs fois pour plusieurs postes en parallèle.")
    remplacer = forms.BooleanField(label="Remplacer les créneaux existants sans inscrit", required=False)
    appliquer_serie = forms.BooleanField(label="Faire de même pour les occurrences suivantes de la série",
                                         required=False)


class CreneauForm(forms.ModelForm):
    debut = ChampDateHeure(label="Début")
    fin = ChampDateHeure(label="Fin")

    class Meta:
        model = Creneau
        fields = ["libelle", "debut", "fin", "besoin"]

    def clean(self):
        donnees = super().clean()
        if donnees.get("debut") and donnees.get("fin") and donnees["fin"] <= donnees["debut"]:
            self.add_error("fin", "La fin doit être après le début.")
        return donnees


class DisponibiliteForm(forms.ModelForm):
    class Meta:
        model = Disponibilite
        fields = ["date", "heure_debut", "heure_fin", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "heure_debut": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "heure_fin": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }


class SondageForm(forms.ModelForm):
    destinataires_membres = ChoixMembres(label="Membres")
    destinataires_groupes = ChoixGroupes(label="Groupes")

    class Meta:
        model = Sondage
        fields = ["type", "titre", "description", "choix_multiples", "date_limite"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "date_limite": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def destinataires(self):
        return membres_choisis(self.cleaned_data, "destinataires_membres", "destinataires_groupes")


class OptionForm(forms.Form):
    libelle = forms.CharField(label="Réponse proposée", max_length=200, required=False)
    date = forms.DateField(label="Date", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    heure_debut = forms.TimeField(label="De", required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    heure_fin = forms.TimeField(label="À", required=False, widget=forms.TimeInput(attrs={"type": "time"}))


OptionsFormSet = forms.formset_factory(OptionForm, extra=6, max_num=40)


class CanalForm(forms.ModelForm):
    class Meta:
        model = Canal
        fields = ["nom", "description"]


class PreferencesForm(forms.ModelForm):
    class Meta:
        model = Preferences
        fields = ["email_invitations", "email_sondages", "email_urgences", "email_evenements", "email_messages"]
        widgets = {"email_messages": forms.RadioSelect}
