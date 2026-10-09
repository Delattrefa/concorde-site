from django.urls import path

from . import views

app_name = "newsletter"

urlpatterns = [
    path("confirmer/<uuid:jeton>/", views.confirmer, name="confirmer"),
    path("desinscription/<uuid:jeton>/", views.desinscription, name="desinscription"),
    path("lire/<int:pk>/", views.lire, name="lire"),
]
