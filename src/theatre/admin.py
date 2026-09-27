from django.contrib import admin
from .models import (
    Representation, Reservation, PlanSalle, PlaceReservee, Ticket,
    PlaceLibre, VenteFlash, ZoneTampon
)


@admin.register(Representation)
class RepresentationAdmin(admin.ModelAdmin):
    list_display = ('nom', 'date', 'prix_adulte', 'prix_enfant', 'total_reservations')
    list_filter = ('date',)
    search_fields = ('nom',)
    date_hierarchy = 'date'


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'representation', 'nb_adultes', 'nb_enfants', 'prix_total', 'created_at')
    list_filter = ('representation', 'preference_rangee', 'preference_cote')
    search_fields = ('nom', 'prenom')
    autocomplete_fields = ['representation']
    readonly_fields = ('prix_total', 'created_at')


@admin.register(PlanSalle)
class PlanSalleAdmin(admin.ModelAdmin):
    list_display = ('representation', 'nb_rangees', 'nb_total_places', 'generated_at')
    readonly_fields = ('generated_at',)


@admin.register(PlaceReservee)
class PlaceReserveeAdmin(admin.ModelAdmin):
    list_display = ('numero_place', 'rangee', 'colonne', 'reservation', 'plan_salle')
    list_filter = ('plan_salle',)
    search_fields = ('reservation__nom', 'reservation__prenom')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display  = ('place', 'statut', 'prix_unitaire', 'imprime_le', 'annule_le')
    list_filter   = ('statut', 'place__plan_salle__representation')
    search_fields = ('place__reservation__nom', 'place__reservation__prenom')
    readonly_fields = ('imprime_le',)
    
@admin.register(PlaceLibre)
class PlaceLibreAdmin(admin.ModelAdmin):
    list_display  = ('numero_place', 'rangee', 'colonne', 'statut', 'plan_salle')
    list_filter   = ('statut', 'plan_salle')

@admin.register(VenteFlash)
class VenteFlashAdmin(admin.ModelAdmin):
    list_display  = ('place_libre', 'nom', 'prenom', 'tarif', 'prix', 'statut', 'vendu_le')
    list_filter   = ('statut', 'tarif')
    search_fields = ('nom', 'prenom')

@admin.register(ZoneTampon)
class ZoneTamponAdmin(admin.ModelAdmin):
    list_display  = ('reservation', 'plan_salle', 'mis_en_tampon_le')
    list_filter   = ('plan_salle',)
