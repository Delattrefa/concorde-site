"""
Sondages du planning : trouver une date (type Doodle : oui / si nécessaire
/ non pour chaque proposition) ou prendre une décision (un ou plusieurs
choix, à la majorité).
"""
from datetime import datetime, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import OptionsFormSet, SondageForm
from .models import Evenement, Notification, OptionSondage, Sondage, Vote, est_responsable, nom_membre


def _visibles(user):
    sondages = Sondage.objects.all()
    if not est_responsable(user):
        sondages = sondages.filter(Q(destinataires=None) | Q(destinataires=user) | Q(createur=user)).distinct()
    return sondages


def _sondage_visible(request, pk):
    sondage = _visibles(request.user).filter(pk=pk).first()
    if sondage is None:
        raise Http404
    return sondage


@login_required
def sondages(request):
    deja_vote = set(Vote.objects.filter(membre=request.user).values_list("option__sondage", flat=True))
    liste = list(_visibles(request.user).select_related("createur", "evenement"))
    for s in liste:
        s.a_vote = s.pk in deja_vote
    return render(request, "planning/sondages.html", {
        "ouverts": [s for s in liste if s.ouvert()],
        "termines": [s for s in liste if not s.ouvert()][:30],
    })


def _options(sondage_type, formset):
    """Options valides du formulaire, ou message d'erreur."""
    options = []
    for form in formset:
        d = form.cleaned_data
        if not d:
            continue
        if sondage_type == Sondage.TYPE_DATE:
            if not d.get("date"):
                continue
            debut = timezone.make_aware(datetime.combine(d["date"], d.get("heure_debut") or time.min))
            fin = timezone.make_aware(datetime.combine(d["date"], d["heure_fin"])) if d.get("heure_fin") else None
            if fin and fin <= debut:
                return None, "Une heure de fin précède son heure de début."
            options.append(OptionSondage(debut=debut, fin=fin))
        elif (d.get("libelle") or "").strip():
            options.append(OptionSondage(libelle=d["libelle"].strip()))
    if len(options) < 2:
        return None, "Proposez au moins deux " + ("dates." if sondage_type == Sondage.TYPE_DATE else "réponses.")
    return options, ""


@login_required
def sondage_nouveau(request):
    evenement = None
    if request.GET.get("evenement"):
        evenement = Evenement.objects.visibles_par(request.user).filter(pk=request.GET["evenement"]).first()
    initial = {"titre": f"{evenement.titre} : quelle date ?"} if evenement else {}
    form = SondageForm(request.POST or None, initial=initial)
    formset = OptionsFormSet(request.POST or None, prefix="options")
    erreur_options = ""
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        options, erreur_options = _options(form.cleaned_data["type"], formset)
        if options:
            with transaction.atomic():
                sondage = form.save(commit=False)
                sondage.createur = request.user
                sondage.evenement = evenement
                sondage.save()
                destinataires = form.destinataires()
                sondage.destinataires.set(destinataires)
                for rang, option in enumerate(options):
                    option.sondage, option.ordre = sondage, rang
                OptionSondage.objects.bulk_create(options)
            cibles = destinataires or services.membres_actifs().values_list("pk", flat=True)
            services.notifier(cibles, Notification.SONDAGE, f"Nouveau sondage de {nom_membre(request.user)} : {sondage.titre}",
                              sondage.get_absolute_url(), exclure=request.user)
            messages.success(request, "Sondage créé : vous pouvez déjà y répondre.")
            return redirect(sondage)
    return render(request, "planning/sondage_form.html", {
        "form": form, "formset": formset, "erreur_options": erreur_options, "evenement": evenement,
    })


@login_required
def sondage(request, pk):
    sondage = _sondage_visible(request, pk)
    options = list(sondage.options.prefetch_related("votes__membre"))
    votants, mes_reponses = {}, {}
    for option in options:
        option.reponses = {v.membre_id: v.reponse for v in option.votes.all()}
        option.nb_oui = sum(1 for r in option.reponses.values() if r == Vote.OUI)
        option.nb_si_besoin = sum(1 for r in option.reponses.values() if r == Vote.SI_BESOIN)
        option.score = option.nb_oui + option.nb_si_besoin / 2
        for v in option.votes.all():
            votants[v.membre_id] = v.membre
        if request.user.pk in option.reponses:
            mes_reponses[option.pk] = option.reponses[request.user.pk]
    meilleur = max((o.score for o in options), default=0)
    for option in options:
        option.meilleur = meilleur > 0 and option.score == meilleur
    lignes = [
        {"membre": m, "nom": nom_membre(m), "reponses": [o.reponses.get(m.pk, "") for o in options],
         "choix": [o.libelle for o in options if o.reponses.get(m.pk) == Vote.OUI]}
        for m in sorted(votants.values(), key=nom_membre) if m.pk != request.user.pk
    ]
    return render(request, "planning/sondage_detail.html", {
        "sondage": sondage,
        "options": options,
        "lignes": lignes,
        "mes_reponses": mes_reponses,
        "ma_ligne": [(o, mes_reponses.get(o.pk, "")) for o in options],
        "a_vote": bool(mes_reponses),
        "nb_votants": len(votants),
        "peut_modifier": sondage.peut_modifier(request.user),
        "destinataires": sondage.destinataires.all(),
        "reponses": Vote.REPONSES,
    })


@login_required
@require_POST
def sondage_voter(request, pk):
    sondage = _sondage_visible(request, pk)
    if not sondage.ouvert():
        messages.error(request, "Ce sondage est clôturé.")
        return redirect(sondage)
    options = {str(o.pk): o for o in sondage.options.all()}
    votes = []
    if sondage.type == Sondage.TYPE_DATE:
        for cle, option in options.items():
            reponse = request.POST.get(f"option_{cle}", Vote.NON)
            if reponse not in dict(Vote.REPONSES):
                reponse = Vote.NON
            votes.append(Vote(option=option, membre=request.user, reponse=reponse))
    else:
        choix = [c for c in request.POST.getlist("choix") if c in options]
        if not sondage.choix_multiples:
            choix = choix[:1]
        if not choix:
            messages.error(request, "Cochez au moins une réponse.")
            return redirect(sondage)
        votes = [Vote(option=options[c], membre=request.user, reponse=Vote.OUI) for c in choix]
    with transaction.atomic():
        Vote.objects.filter(option__sondage=sondage, membre=request.user).delete()
        Vote.objects.bulk_create(votes)
    messages.success(request, "Merci, votre réponse est enregistrée.")
    return redirect(sondage)


@login_required
@require_POST
def sondage_clore(request, pk):
    sondage = get_object_or_404(Sondage, pk=pk)
    if not sondage.peut_modifier(request.user):
        raise PermissionDenied
    sondage.clos = not sondage.clos
    sondage.save(update_fields=["clos"])
    messages.success(request, "Sondage clôturé." if sondage.clos else "Sondage rouvert.")
    return redirect(sondage)


@login_required
@require_POST
def sondage_supprimer(request, pk):
    sondage = get_object_or_404(Sondage, pk=pk)
    if not sondage.peut_modifier(request.user):
        raise PermissionDenied
    sondage.delete()
    messages.success(request, "Sondage supprimé.")
    return redirect("planning:sondages")
