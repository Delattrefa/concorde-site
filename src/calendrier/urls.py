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
    path("reservation/ajouter/", views.ReservationAdminCreateView.as_view(), name="reservation_ajouter"),
    path("reservations/", views.ReservationListView.as_view(), name="reservation_liste"),
    path("reservation/<int:pk>/", views.ReservationDetailView.as_view(), name="reservation_detail"),
    path("reservation/<int:pk>/modifier/", views.ReservationUpdateView.as_view(), name="reservation_modifier"),
    path("reservation/<int:pk>/traiter/", views.reservation_traiter, name="reservation_traiter"),
    path("reservation/<int:pk>/supprimer/", views.ReservationDeleteView.as_view(), name="reservation_supprimer"),
    path("reservation/<int:reservation_pk>/contrat/", views.rediger_contrat, name="reservation_contrat"),
    path("reservation/<int:reservation_pk>/contrat/pdf/", views.telecharger_contrat, name="reservation_contrat_pdf"),

    # --- Suivi des paiements des locations (administrateurs) ---------------
    path("reservation/paiements/", views.suivi_paiements, name="suivi_paiements"),

    # --- Contrat-type : articles et annexes (administrateurs) ---------------
    path("contrat-type/", views.modele_contrat, name="modele_contrat"),
    path("contrat-type/apercu/", views.apercu_modele_contrat, name="modele_contrat_apercu"),
    path("contrat-type/article/ajouter/", views.ArticleContratCreateView.as_view(), name="article_contrat_ajouter"),
    path("contrat-type/article/<int:pk>/modifier/", views.ArticleContratUpdateView.as_view(), name="article_contrat_modifier"),
    path("contrat-type/article/<int:pk>/supprimer/", views.ArticleContratDeleteView.as_view(), name="article_contrat_supprimer"),
    path("contrat-type/annexe/ajouter/", views.AnnexeContratCreateView.as_view(), name="annexe_contrat_ajouter"),
    path("contrat-type/annexe/<int:pk>/modifier/", views.AnnexeContratUpdateView.as_view(), name="annexe_contrat_modifier"),
    path("contrat-type/annexe/<int:pk>/supprimer/", views.AnnexeContratDeleteView.as_view(), name="annexe_contrat_supprimer"),
]
