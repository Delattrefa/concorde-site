"""
Vues publiques de la newsletter : inscription (page Wagtail), confirmation
(double opt-in), désinscription et version web d'une newsletter envoyée.
"""
import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from concorde_site.antispam import compter_envoi, limite_atteinte

from .forms import InscriptionForm
from .models import Abonne, Newsletter, url_absolue
from .rendu import personnaliser, rendre_newsletter

logger = logging.getLogger("newsletter")

LIMITE_PAR_IP = 10        # inscriptions par heure et par adresse IP


def _est_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _envoyer_confirmation(abonne, page):
    lien = url_absolue(reverse("newsletter:confirmer", args=[abonne.jeton]))
    corps = (
        f"Bonjour{(' ' + abonne.prenom) if abonne.prenom else ''},\n\n"
        "Vous avez demandé à recevoir la newsletter de La Concorde asbl.\n"
        "Pour confirmer votre inscription, cliquez sur ce lien :\n\n"
        f"{lien}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet e-mail : "
        "vous ne recevrez rien.\n\nLa Concorde asbl\n"
    )
    send_mail(
        "Confirmez votre inscription à la newsletter de La Concorde",
        corps,
        getattr(settings, "NEWSLETTER_FROM_EMAIL", None) or settings.DEFAULT_FROM_EMAIL,
        [abonne.email],
    )


def _inscrire(form, page):
    """Enregistre l'inscription. Renvoie (succès, message)."""
    donnees = form.cleaned_data
    abonne, cree = Abonne.objects.get_or_create(
        email=donnees["email"],
        defaults={
            "prenom": donnees["prenom"], "nom": donnees["nom"],
            "source": Abonne.SOURCE_FORMULAIRE,
            "statut": Abonne.STATUT_ATTENTE if page.confirmation_par_email else Abonne.STATUT_ACTIF,
        },
    )
    if not cree:
        if donnees["prenom"]:
            abonne.prenom = donnees["prenom"]
        if donnees["nom"]:
            abonne.nom = donnees["nom"]
        if abonne.statut != Abonne.STATUT_ACTIF:
            # Réinscription (après désinscription) : nouveau consentement.
            abonne.statut = Abonne.STATUT_ATTENTE if page.confirmation_par_email else Abonne.STATUT_ACTIF
            abonne.source = Abonne.SOURCE_FORMULAIRE
            abonne.date_inscription = timezone.now()
            abonne.date_confirmation = None
        abonne.save()

    if abonne.statut == Abonne.STATUT_ATTENTE:
        try:
            _envoyer_confirmation(abonne, page)
        except Exception:
            logger.exception("Envoi de l'e-mail de confirmation impossible (%s)", abonne.email)
            return False, ("Votre inscription n'a pas pu être finalisée : l'e-mail de confirmation "
                           "n'a pas pu être envoyé. Merci de réessayer plus tard.")
        return True, ("Presque fini ! Un e-mail de confirmation vient de vous être envoyé : "
                      "cliquez sur le lien qu'il contient pour activer votre inscription.")
    # Même message qu'il s'agisse d'une nouvelle inscription ou non : on ne
    # révèle pas si une adresse est déjà abonnée.
    return True, page.message_succes


def servir_page_inscription(page, request, *args, **kwargs):
    contexte = page.get_context(request, *args, **kwargs)

    if request.method == "POST":
        form = InscriptionForm(request.POST, texte_consentement=page.texte_consentement)

        if form.est_un_robot:
            succes, message = True, page.message_succes          # robot : on fait semblant
        elif limite_atteinte(request, "newsletter-inscription", LIMITE_PAR_IP):
            succes, message = False, "Trop de tentatives depuis votre connexion. Réessayez dans une heure."
        elif form.is_valid():
            compter_envoi(request, "newsletter-inscription")
            succes, message = _inscrire(form, page)
        else:
            succes, message = False, "Merci de corriger le formulaire."

        if _est_ajax(request):
            erreurs = {champ: [str(e) for e in liste] for champ, liste in form.errors.items()} if not succes else {}
            return JsonResponse({"succes": succes, "message": message, "erreurs": erreurs},
                                status=200 if succes else 400)

        if succes:
            messages.success(request, message)
            return redirect(page.url + "#inscription")
        messages.error(request, message)
        contexte["form"] = form
    else:
        contexte["form"] = InscriptionForm(texte_consentement=page.texte_consentement)

    return TemplateResponse(request, page.get_template(request, *args, **kwargs), contexte)


def confirmer(request, jeton):
    """Lien reçu par e-mail (double opt-in) : active l'inscription."""
    abonne = get_object_or_404(Abonne, jeton=jeton)
    deja = abonne.statut == Abonne.STATUT_ACTIF
    if abonne.statut == Abonne.STATUT_ATTENTE:
        abonne.statut = Abonne.STATUT_ACTIF
        abonne.date_confirmation = timezone.now()
        abonne.save()
    return TemplateResponse(request, "newsletter/message.html", {
        "titre": "Inscription confirmée" if abonne.statut == Abonne.STATUT_ACTIF else "Lien expiré",
        "texte": (
            "Votre inscription était déjà active. Merci !" if deja else
            "Merci ! Vous recevrez désormais la newsletter de La Concorde asbl."
            if abonne.statut == Abonne.STATUT_ACTIF else
            "Cette inscription a été annulée. Vous pouvez vous réinscrire depuis le site."
        ),
    })


@csrf_exempt
def desinscription(request, jeton):
    """Lien de désinscription personnel.

    GET : page de confirmation (un simple clic sur un lien, ou l'analyse
    automatique d'un antivirus, ne désinscrit pas).
    POST : désinscription. Accepte aussi la désinscription « en un clic »
    des messageries (Gmail, Apple Mail), qui envoient un POST sans jeton CSRF :
    le jeton personnel, secret et unique, protège la requête."""
    abonne = Abonne.objects.filter(jeton=jeton).first()
    if abonne is None:
        return TemplateResponse(request, "newsletter/message.html", {
            "titre": "Lien inconnu",
            "texte": "Ce lien de désinscription n'est plus valable. Vous n'êtes peut-être plus inscrit(e).",
        }, status=404)

    if request.method == "POST":
        if abonne.statut != Abonne.STATUT_DESINSCRIT:
            abonne.desinscrire()
            logger.info("Désinscription : %s", abonne.email)
        if request.POST.get("List-Unsubscribe") == "One-Click":
            return HttpResponse("Désinscription enregistrée.", content_type="text/plain; charset=utf-8")
        return TemplateResponse(request, "newsletter/message.html", {
            "titre": "Vous êtes désinscrit(e)",
            "texte": f"L'adresse {abonne.email} ne recevra plus la newsletter de La Concorde asbl.",
        })

    return TemplateResponse(request, "newsletter/desinscription.html", {"abonne": abonne})


def lire(request, pk):
    """Version web d'une newsletter (lien « Ouvrez-la dans votre navigateur »)."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    if newsletter.statut == Newsletter.STATUT_BROUILLON and not request.user.is_staff:
        raise Http404
    contenu_html, _ = rendre_newsletter(newsletter)
    # Version publique : pas de lien personnel, on renvoie vers la page de
    # la newsletter (où se trouve l'explication pour se désinscrire).
    from .models import NewsletterPage

    page = NewsletterPage.objects.live().first()
    contenu_html = personnaliser(contenu_html, "", url_absolue(page.url if page else "/"))
    reponse = HttpResponse(contenu_html)
    reponse["X-Robots-Tag"] = "noindex"
    return reponse
