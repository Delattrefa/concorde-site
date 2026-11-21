"""
Discussions (canaux généraux et fil de chaque événement) et notifications.

o2switch n'accepte pas les connexions permanentes (WebSocket) : la page
d'une discussion demande les nouveaux messages toutes les quelques
secondes (planning.js), tant qu'elle est affichée.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import services
from .forms import CanalForm, PreferencesForm
from .models import Canal, Evenement, Lecture, Message, Notification, Preferences, est_responsable, nom_membre

NB_MESSAGES = 50
LONGUEUR_MAX = 4000


def _canal_visible(request, pk):
    canal = get_object_or_404(Canal.objects.select_related("evenement"), pk=pk)
    if not canal.visible_par(request.user):
        raise Http404
    return canal


def _marquer_lu(canal, user, dernier_id):
    if dernier_id:
        lecture, _ = Lecture.objects.get_or_create(canal=canal, membre=user)
        if dernier_id > lecture.dernier_message:
            lecture.dernier_message = dernier_id
            lecture.save(update_fields=["dernier_message"])


def contexte_discussion(canal, user, avant=None):
    """Derniers messages d'un canal, pour la page du canal ou d'un événement."""
    maintenant = timezone.now()
    requete = canal.messages.select_related("auteur")
    if avant:
        requete = requete.filter(pk__lt=avant)
    derniers = list(requete.order_by("-pk")[:NB_MESSAGES + 1])
    plus_anciens = len(derniers) > NB_MESSAGES
    derniers = list(reversed(derniers[:NB_MESSAGES]))
    par_nom = services.membres_par_nom()
    if not avant:
        _marquer_lu(canal, user, derniers[-1].pk if derniers else 0)
    return {
        "canal": canal,
        "messages_canal": [services.message_json(m, par_nom, user) for m in derniers],
        "plus_anciens": derniers[0].pk if plus_anciens and derniers else None,
        "dernier_id": derniers[-1].pk if derniers else 0,
        "maj": maintenant.isoformat(),
        "membres_mention": [{"nom": nom_membre(m), "identifiant": m.username} for m in par_nom.values()],
    }


@login_required
def canaux(request):
    visibles = Evenement.objects.visibles_par(request.user).values("pk")
    liste = list(
        Canal.objects.filter(Q(evenement=None, archive=False) | Q(evenement__in=visibles))
        .annotate(dernier=Max("messages__pk"), nb=Count("messages"))
        .filter(Q(evenement=None) | Q(nb__gt=0))
        .select_related("evenement")
        .order_by("-dernier", "nom")[:60]
    )
    lus = dict(Lecture.objects.filter(membre=request.user, canal__in=liste).values_list("canal", "dernier_message"))
    for canal in liste:
        canal.non_lus = canal.messages.filter(pk__gt=lus.get(canal.pk, 0)).count() if canal.dernier else 0
        canal.dernier_message = canal.messages.select_related("auteur").order_by("-pk").first() if canal.dernier else None
    return render(request, "planning/canaux.html", {
        "generaux": [c for c in liste if not c.evenement_id],
        "evenements": [c for c in liste if c.evenement_id],
        "est_responsable": est_responsable(request.user),
    })


@login_required
def canal_nouveau(request):
    if not est_responsable(request.user):
        raise PermissionDenied
    form = CanalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        canal = form.save()
        messages.success(request, f"Canal « {canal.nom} » créé.")
        return redirect(canal)
    return render(request, "planning/canal_form.html", {"form": form})


@login_required
def canal(request, pk):
    canal = _canal_visible(request, pk)
    if canal.evenement_id:
        return redirect(canal.get_absolute_url())
    avant = request.GET.get("avant")
    contexte = contexte_discussion(canal, request.user, int(avant) if avant and avant.isdigit() else None)
    contexte["est_responsable"] = est_responsable(request.user)
    return render(request, "planning/canal.html", contexte)


@login_required
def canal_messages(request, pk):
    """GET ?apres=<id> : nouveaux messages (JSON). POST : publier."""
    canal = _canal_visible(request, pk)
    if request.method == "POST":
        texte = request.POST.get("texte", "").strip()[:LONGUEUR_MAX]
        ajax = request.headers.get("X-Requested-With") == "fetch"
        if texte:
            message = services.publier(canal, request.user, texte)
            _marquer_lu(canal, request.user, message.pk)
            if ajax:
                return JsonResponse({"message": services.message_json(message, services.membres_par_nom(), request.user)})
        elif ajax:
            return JsonResponse({"erreur": "Message vide."}, status=400)
        return redirect(canal.get_absolute_url())
    apres = request.GET.get("apres", "0")
    apres = int(apres) if apres.isdigit() else 0
    maintenant = timezone.now()
    nouveaux = list(canal.messages.filter(pk__gt=apres).select_related("auteur").order_by("pk")[:100])
    reponse = {"maj": maintenant.isoformat()}
    # Messages déjà affichés : lesquels existent encore, lesquels ont été modifiés
    premier = request.GET.get("premier", "")
    modifies = []
    if premier.isdigit() and apres:
        affiches = canal.messages.filter(pk__gte=int(premier), pk__lte=apres)
        reponse["existants"] = list(affiches.values_list("pk", flat=True))
        depuis = parse_datetime(request.GET.get("maj", ""))
        if depuis:
            modifies = list(affiches.filter(modifie_le__gte=depuis).select_related("auteur"))
    par_nom = services.membres_par_nom() if nouveaux or modifies else {}
    if nouveaux:
        _marquer_lu(canal, request.user, nouveaux[-1].pk)
    reponse["messages"] = [services.message_json(m, par_nom, request.user) for m in nouveaux]
    reponse["modifies"] = [services.message_json(m, par_nom, request.user) for m in modifies]
    return JsonResponse(reponse)


@login_required
@require_POST
def canal_archiver(request, pk):
    if not est_responsable(request.user):
        raise PermissionDenied
    canal = get_object_or_404(Canal, pk=pk, evenement=None)
    canal.archive = not canal.archive
    canal.save(update_fields=["archive"])
    messages.success(request, "Canal archivé." if canal.archive else "Canal rétabli.")
    return redirect("planning:canaux")


def _mon_message(request, pk):
    """Un message ne se modifie ou ne se supprime que par son auteur."""
    message = get_object_or_404(Message.objects.select_related("canal", "auteur"), pk=pk)
    if message.auteur_id != request.user.pk or not message.canal.visible_par(request.user):
        raise PermissionDenied
    return message


@login_required
@require_POST
def message_modifier(request, pk):
    message = _mon_message(request, pk)
    texte = request.POST.get("texte", "").strip()[:LONGUEUR_MAX]
    ajax = request.headers.get("X-Requested-With") == "fetch"
    if not texte:
        if ajax:
            return JsonResponse({"erreur": "Message vide."}, status=400)
        return redirect(message.canal.get_absolute_url())
    if texte != message.texte:
        services.modifier_message(message, texte)
    if ajax:
        return JsonResponse({"message": services.message_json(message, services.membres_par_nom(), request.user)})
    return redirect(message.canal.get_absolute_url())


@login_required
@require_POST
def message_supprimer(request, pk):
    message = _mon_message(request, pk)
    canal = message.canal
    message.delete()
    if request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse({"supprime": pk})
    return redirect(canal.get_absolute_url())


# --- Notifications ----------------------------------------------------------

@login_required
def notifications(request):
    preferences = Preferences.de(request.user)
    form = PreferencesForm(request.POST or None, instance=preferences)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Préférences enregistrées.")
        return redirect("planning:notifications")
    return render(request, "planning/notifications.html", {
        "notifications": request.user.notifications_planning.all()[:100],
        "form": form,
        "sans_email": not request.user.email,
    })


@login_required
def notification_ouvrir(request, pk):
    notification = get_object_or_404(Notification, pk=pk, destinataire=request.user)
    if not notification.lue:
        notification.lue = True
        notification.save(update_fields=["lue"])
    lien = notification.lien
    if not url_has_allowed_host_and_scheme(lien, allowed_hosts={request.get_host()}) or not lien.startswith("/"):
        lien = "/planning/"
    return redirect(lien)


@login_required
@require_POST
def notifications_tout_lu(request):
    request.user.notifications_planning.filter(lue=False).update(lue=True)
    return redirect("planning:notifications")


@login_required
def notifications_compte(request):
    return JsonResponse({"non_lues": request.user.notifications_planning.filter(lue=False).count()})
