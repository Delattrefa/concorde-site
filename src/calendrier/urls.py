"""
URLs de l'application 'calendrier'.
Préfixe monté dans concorde_site/urls.py : /calendrier/
"""
from django.urls import path

from . import views

app_name = "calendrier"

urlpatterns = [
    # --- Calendrier mensuel (page principale de l'application) -----------
    path("", views.CalendrierMoisView.as_view(), name="mois_courant"),
    path("<int:annee>/<int:mois>/", views.CalendrierMoisView.as_view(), name="mois"),
    path("aller-a/", views.aller_a_mois, name="aller_a_mois"),
    path("<int:annee>/<int:mois>/<int:jour>/", views.jour_action, name="jour_action"),

    # --- CRUD Activités ----------------------------------------------------
    path("activite/ajouter/", views.ActiviteCreateView.as_view(), name="activite_ajouter"),
    path("activite/<int:pk>/", views.ActiviteDetailView.as_view(), name="activite_detail"),
    path("activite/<int:pk>/modifier/", views.ActiviteUpdateView.as_view(), name="activite_modifier"),
    path("activite/<int:pk>/supprimer/", views.ActiviteDeleteView.as_view(), name="activite_supprimer"),

    # --- CRUD Réservations ---------------------------------------------------
    path("reservation/demander/", views.ReservationCreateView.as_view(), name="reservation_demander"),
    path("reservations/", views.ReservationListView.as_view(), name="reservation_liste"),
    path("reservation/<int:pk>/", views.ReservationDetailView.as_view(), name="reservation_detail"),
    path("reservation/<int:pk>/modifier/", views.ReservationUpdateView.as_view(), name="reservation_modifier"),
    path("reservation/<int:pk>/traiter/", views.reservation_traiter, name="reservation_traiter"),
    path("reservation/<int:pk>/supprimer/", views.ReservationDeleteView.as_view(), name="reservation_supprimer"),
    path("reservation/<int:reservation_pk>/contrat/", views.rediger_contrat, name="reservation_contrat"),
    path("reservation/<int:reservation_pk>/contrat/pdf/", views.telecharger_contrat, name="reservation_contrat_pdf"),
]
