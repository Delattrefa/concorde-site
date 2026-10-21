from django.urls import path

from . import views, views_discussion, views_sondages

app_name = "planning"

urlpatterns = [
    # Agenda
    path("", views.mois, name="accueil"),
    path("mois/<int:annee>/<int:mois>/", views.mois, name="mois"),
    path("semaine/<int:annee>/<int:mois>/<int:jour>/", views.semaine, name="semaine"),
    path("jour/<int:annee>/<int:mois>/<int:jour>/", views.jour, name="jour"),
    path("liste/", views.liste, name="liste"),

    # Événements, invitations, créneaux
    path("evenement/ajouter/", views.evenement_ajouter, name="evenement_ajouter"),
    path("evenement/<int:pk>/", views.evenement, name="evenement"),
    path("evenement/<int:pk>/modifier/", views.evenement_modifier, name="evenement_modifier"),
    path("evenement/<int:pk>/annuler/", views.evenement_annuler, name="evenement_annuler"),
    path("evenement/<int:pk>/supprimer/", views.evenement_supprimer, name="evenement_supprimer"),
    path("evenement/<int:pk>/inviter/", views.evenement_inviter, name="evenement_inviter"),
    path("evenement/<int:pk>/repondre/", views.evenement_repondre, name="evenement_repondre"),
    path("evenement/<int:pk>/creneaux/decouper/", views.creneaux_decouper, name="creneaux_decouper"),
    path("evenement/<int:pk>/creneaux/ajouter/", views.creneau_ajouter, name="creneau_ajouter"),
    path("creneau/<int:pk>/modifier/", views.creneau_modifier, name="creneau_modifier"),
    path("creneau/<int:pk>/supprimer/", views.creneau_supprimer, name="creneau_supprimer"),
    path("creneau/<int:pk>/inscrire/", views.creneau_inscrire, name="creneau_inscrire"),
    path("creneau/<int:pk>/desinscrire/", views.creneau_desinscrire, name="creneau_desinscrire"),
    path("invitations/", views.invitations, name="invitations"),

    # Besoins et disponibilités
    path("a-combler/", views.couverture, name="couverture"),
    path("disponibilites/", views.disponibilites, name="disponibilites"),
    path("disponibilites/<int:pk>/supprimer/", views.disponibilite_supprimer, name="disponibilite_supprimer"),

    # Sondages
    path("sondages/", views_sondages.sondages, name="sondages"),
    path("sondages/nouveau/", views_sondages.sondage_nouveau, name="sondage_nouveau"),
    path("sondages/<int:pk>/", views_sondages.sondage, name="sondage"),
    path("sondages/<int:pk>/voter/", views_sondages.sondage_voter, name="sondage_voter"),
    path("sondages/<int:pk>/clore/", views_sondages.sondage_clore, name="sondage_clore"),
    path("sondages/<int:pk>/supprimer/", views_sondages.sondage_supprimer, name="sondage_supprimer"),

    # Discussions
    path("discussions/", views_discussion.canaux, name="canaux"),
    path("discussions/nouveau/", views_discussion.canal_nouveau, name="canal_nouveau"),
    path("discussions/<int:pk>/", views_discussion.canal, name="canal"),
    path("discussions/<int:pk>/messages/", views_discussion.canal_messages, name="canal_messages"),
    path("discussions/<int:pk>/archiver/", views_discussion.canal_archiver, name="canal_archiver"),
    path("message/<int:pk>/supprimer/", views_discussion.message_supprimer, name="message_supprimer"),

    # Notifications
    path("notifications/", views_discussion.notifications, name="notifications"),
    path("notifications/<int:pk>/", views_discussion.notification_ouvrir, name="notification_ouvrir"),
    path("notifications/tout-lu/", views_discussion.notifications_tout_lu, name="notifications_tout_lu"),
    path("notifications/compte/", views_discussion.notifications_compte, name="notifications_compte"),
]
