"""
Interface d'administration Django (django-admin, distincte de l'admin
Wagtail) pour l'application 'calendrier'.
"""
from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import Activite, AnnexeContrat, ArticleContrat, ContratLocation, Reservation


@admin.register(Activite)
class ActiviteAdmin(admin.ModelAdmin):
    """Gestion des activités dans l'admin Django."""

    list_display = ("nom", "date_debut", "date_fin", "visibilite", "couleur_apercu", "auteur")
    list_filter = ("visibilite", "date_debut")
    search_fields = ("nom", "description", "auteur__username", "auteur__email")
    date_hierarchy = "date_debut"
    autocomplete_fields = ["auteur"]
    readonly_fields = ("date_creation",)

    fieldsets = (
        ("Informations générales", {
            "fields": ("nom", "description", "auteur"),
        }),
        ("Dates", {
            "fields": ("date_debut", "date_fin"),
        }),
        ("Affichage", {
            "fields": ("visibilite", "couleur"),
        }),
        ("Suivi", {
            "fields": ("date_creation",),
        }),
    )

    @admin.display(description="Couleur")
    def couleur_apercu(self, obj):
        """Affiche un petit aperçu coloré dans la liste, plutôt que le code
        hexadécimal brut."""
        return format_html(
            '<span style="display:inline-block;width:16px;height:16px;'
            'border-radius:3px;background:{};border:1px solid #999;"></span> {}',
            obj.couleur,
            obj.couleur,
        )


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    """Gestion des demandes de réservation de salle dans l'admin Django,
    avec actions groupées de validation/refus."""

    list_display = ("nom", "prenom", "date_debut", "date_fin", "email", "telephone", "statut", "date_demande", "traite_par")
    list_filter = ("statut", "date_debut")
    search_fields = ("nom", "prenom", "telephone", "email", "adresse")
    date_hierarchy = "date_debut"
    readonly_fields = ("date_demande", "traite_par", "date_traitement")
    actions = ["valider_les_reservations", "refuser_les_reservations"]

    fieldsets = (
        ("Demandeur", {
            "fields": ("nom", "prenom", "adresse", "email", "telephone"),
        }),
        ("Demande", {
            "fields": ("date_debut", "date_fin", "message"),
        }),
        ("Traitement administratif", {
            "fields": ("statut", "traite_par", "date_traitement", "date_demande"),
        }),
    )

    @admin.action(description="Valider les réservations sélectionnées")
    def valider_les_reservations(self, request, queryset):
        nb_maj = queryset.update(
            statut=Reservation.STATUT_VALIDEE,
            traite_par=request.user,
            date_traitement=timezone.now(),
        )
        self.message_user(request, f"{nb_maj} réservation(s) validée(s).")

    @admin.action(description="Refuser les réservations sélectionnées")
    def refuser_les_reservations(self, request, queryset):
        nb_maj = queryset.update(
            statut=Reservation.STATUT_REFUSEE,
            traite_par=request.user,
            date_traitement=timezone.now(),
        )
        self.message_user(request, f"{nb_maj} réservation(s) refusée(s).")


@admin.register(ContratLocation)
class ContratLocationAdmin(admin.ModelAdmin):
    """Consultation des contrats de location générés (lecture principalement :
    la rédaction se fait depuis la fiche de la réservation, sur le site)."""

    list_display = ("reservation", "delegue_prenom", "delegue_nom", "montant_location", "montant_caution", "date_creation")
    search_fields = ("reservation__nom", "reservation__prenom", "delegue_nom", "delegue_prenom")
    readonly_fields = ("date_creation", "genere_par")
    autocomplete_fields = ["reservation"]


@admin.register(ArticleContrat)
class ArticleContratAdmin(admin.ModelAdmin):
    """Articles du contrat-type (également modifiables sur le site :
    /calendrier/contrat-type/)."""

    list_display = ("titre", "ordre", "actif", "date_modification")
    list_editable = ("ordre", "actif")
    search_fields = ("titre", "texte")


@admin.register(AnnexeContrat)
class AnnexeContratAdmin(admin.ModelAdmin):
    """Annexes PDF du contrat-type."""

    list_display = ("titre", "ordre", "actif", "fichier", "date_modification")
    list_editable = ("ordre", "actif")
