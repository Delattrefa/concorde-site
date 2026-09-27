from django.urls import path
from . import views

urlpatterns = [
    # Représentations
    path('', views.representation_list_create, name='representation_list'),
    path('representation/<int:pk>/supprimer/', views.representation_delete, name='representation_delete'),

    # Réservations
    path('reservation/nouvelle/<int:rep_pk>/', views.reservation_create, name='reservation_create'),
    path('reservations/', views.reservation_list, name='reservation_list'),
    path('reservation/<int:pk>/modifier/', views.reservation_edit, name='reservation_edit'),
    path('reservation/<int:pk>/supprimer/', views.reservation_delete, name='reservation_delete'),

    # API prix
    path('api/prix/', views.get_prix, name='get_prix'),

    # Plan de salle
    path('plan/<int:rep_pk>/generer/', views.plan_salle_generer, name='plan_salle_generer'),
    path('plan/<int:rep_pk>/', views.plan_salle_afficher, name='plan_salle_afficher'),

    # Liste imprimable des places
    path('plan/<int:rep_pk>/imprimer/', views.liste_places_imprimer, name='liste_places_imprimer'),

    # Contrôle d'entrée
    path('entree/<int:rep_pk>/', views.controle_entree, name='controle_entree'),
    path('entree/<int:rep_pk>/valider/', views.valider_entree, name='valider_entree'),
    path('ticket/<int:ticket_id>/annuler/', views.annuler_ticket, name='annuler_ticket'),
    path('entree/<int:rep_pk>/tickets/', views.liste_tickets, name='liste_tickets'),
    
    # Vente flash
    path('plan/<int:plan_pk>/vente-flash/',         views.vente_flash,          name='vente_flash'),
    path('vente-flash/<int:vente_id>/annuler/',     views.annuler_vente_flash,  name='annuler_vente_flash'),

    # Zone tampon et déplacement
    path('plan/<int:plan_pk>/mettre-en-tampon/',    views.mettre_en_tampon,     name='mettre_en_tampon'),
    path('plan/<int:plan_pk>/placer-depuis-tampon/',views.placer_depuis_tampon, name='placer_depuis_tampon'),
    path('tampon/<int:tampon_id>/retirer/',         views.retirer_du_tampon,    name='retirer_du_tampon'),
]