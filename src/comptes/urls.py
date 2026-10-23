from django.urls import path

from . import views

app_name = "comptes"

urlpatterns = [
    path("<str:jeton>/", views.inscription, name="inscription"),
]
