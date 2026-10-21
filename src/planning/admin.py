from django.contrib import admin

from .models import Canal, Evenement, Sondage


@admin.register(Evenement)
class EvenementAdmin(admin.ModelAdmin):
    list_display = ["titre", "type", "debut", "fin", "annule", "createur"]
    list_filter = ["type", "annule"]
    search_fields = ["titre", "description", "lieu"]
    date_hierarchy = "debut"


@admin.register(Sondage)
class SondageAdmin(admin.ModelAdmin):
    list_display = ["titre", "type", "createur", "cree_le", "clos"]
    list_filter = ["type", "clos"]


@admin.register(Canal)
class CanalAdmin(admin.ModelAdmin):
    list_display = ["nom", "evenement", "archive"]
    list_filter = ["archive"]
