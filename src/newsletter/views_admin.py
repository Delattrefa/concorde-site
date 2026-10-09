"""
Vues de l'admin Wagtail pour l'envoi d'une newsletter :
- préparation : récapitulatif, e-mail de test, confirmation explicite ;
- suivi : progression, échecs, envoi manuel d'un lot, annulation.
"""
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .envoi import (
    annuler_envoi,
    destinataires_possibles,
    envoi_actif,
    envois_derniere_heure,
    envoyer_test,
    lancer_envoi,
    traiter_lot,
)
from .forms import valider_email_strict
from .models import Envoi, Livraison, Newsletter

MAX_ADRESSES_TEST = 5


def _verifier_droit(request):
    if not request.user.has_perm("newsletter.envoyer_newsletter"):
        raise PermissionDenied


def envoyer(request, pk):
    _verifier_droit(request)
    newsletter = get_object_or_404(Newsletter, pk=pk)
    if envoi_actif(newsletter):
        return redirect("newsletter_admin:suivi", pk=newsletter.pk)

    nb_destinataires = destinataires_possibles(newsletter).count()
    adresses_test = request.POST.get("adresses_test", request.user.email or "")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "test":
            adresses = [a.strip().lower() for a in adresses_test.replace(";", ",").replace("\n", ",").split(",") if a.strip()]
            try:
                if not adresses:
                    raise ValidationError("Indiquez au moins une adresse.")
                if len(adresses) > MAX_ADRESSES_TEST:
                    raise ValidationError(f"{MAX_ADRESSES_TEST} adresses de test au maximum.")
                for adresse in adresses:
                    valider_email_strict(adresse)
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
            else:
                try:
                    nb = envoyer_test(newsletter, adresses)
                except Exception as exc:  # erreur SMTP : on l'affiche telle quelle
                    messages.error(request, f"L'e-mail de test n'a pas pu être envoyé : {exc}")
                else:
                    messages.success(request, f"E-mail de test envoyé à {nb} adresse(s) : {', '.join(adresses)}.")

        elif action == "lancer":
            if request.POST.get("confirmation") != "oui":
                messages.error(request, "Cochez la case de confirmation pour lancer l'envoi.")
            elif nb_destinataires == 0:
                messages.error(request, "Aucun destinataire : tous les abonnés actifs l'ont déjà reçue.")
            else:
                envoi = lancer_envoi(newsletter, request.user)
                messages.success(
                    request,
                    f"Envoi lancé vers {envoi.livraisons.count()} abonné(s). Il se poursuit automatiquement "
                    "par petits lots ; vous pouvez fermer cette page.",
                )
                return redirect("newsletter_admin:suivi", pk=newsletter.pk)

    return TemplateResponse(request, "newsletter/admin/envoyer.html", {
        "newsletter": newsletter,
        "nb_destinataires": nb_destinataires,
        "deja_envoyee": newsletter.statut != Newsletter.STATUT_BROUILLON,
        "adresses_test": adresses_test,
        "url_apercu": reverse("newsletter:lire", args=[newsletter.pk]),
        "url_modifier": reverse("wagtailsnippets_newsletter_newsletter:edit", args=[newsletter.pk]),
        "max_adresses_test": MAX_ADRESSES_TEST,
    })


def suivi(request, pk):
    _verifier_droit(request)
    newsletter = get_object_or_404(Newsletter, pk=pk)
    envoi = newsletter.envois.order_by("-date_lancement").first()
    if envoi is None:
        return redirect("newsletter_admin:envoyer", pk=newsletter.pk)

    if request.method == "POST" and envoi.statut == Envoi.STATUT_EN_COURS:
        action = request.POST.get("action")
        if action == "lot":
            # Petit lot, pour ne pas dépasser le délai d'une requête web.
            nb = traiter_lot(taille=10, pause=0.5)
            messages.success(request, f"{nb} message(s) envoyé(s).") if nb else messages.warning(
                request, "Aucun message envoyé (plafond horaire atteint ou erreur du serveur : voir ci-dessous)."
            )
        elif action == "annuler":
            annuler_envoi(envoi)
            messages.warning(request, "Envoi annulé : les messages restants ne seront pas envoyés.")
        return redirect("newsletter_admin:suivi", pk=newsletter.pk)

    compteurs = envoi.compteurs()
    traites = compteurs["envoyes"] + compteurs["echecs"] + compteurs["ignores"]
    return TemplateResponse(request, "newsletter/admin/suivi.html", {
        "newsletter": newsletter,
        "envoi": envoi,
        "compteurs": compteurs,
        "pourcentage": round(100 * traites / compteurs["total"]) if compteurs["total"] else 100,
        "echecs": envoi.livraisons.filter(statut=Livraison.STATUT_ECHEC).order_by("email")[:100],
        "historique": newsletter.envois.order_by("-date_lancement"),
        "envois_derniere_heure": envois_derniere_heure(),
        "url_modifier": reverse("wagtailsnippets_newsletter_newsletter:edit", args=[newsletter.pk]),
        "nouveaux_destinataires": destinataires_possibles(newsletter).count()
        if envoi.statut != Envoi.STATUT_EN_COURS else 0,
    })
