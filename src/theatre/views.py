"""
Vues CRUD de l'application theatre.

Toutes les vues exigent à la fois d'être connecté ET de disposer de la
permission Django 'theatre.acces_application' (voir acces_theatre_requis
ci-dessous, et AccesApplication dans models.py). Un visiteur non connecté
est redirigé vers la page de connexion du site ; un utilisateur connecté
mais non autorisé reçoit une erreur 403 (accès interdit). Les
super-utilisateurs ont toujours accès.
"""

import json
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import permission_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse

from .models import (
    Representation, Reservation, PlanSalle, PlaceReservee, Ticket, PlaceLibre,
    VenteFlash, ZoneTampon
)
from .forms import RepresentationForm, ReservationForm, ReservationEditForm
from .placement import placer_reservations


# Décorateur unique utilisé par toutes les vues de l'application : exige la
# permission dédiée plutôt qu'une simple connexion. Un utilisateur connecté
# sans cette permission obtient une erreur 403 (raise_exception=True) ;
# un visiteur non connecté est d'abord redirigé vers la page de connexion
# du site (login_url), comme avant.
def acces_theatre_requis(vue):
    return permission_required(
        "theatre.acces_application", login_url="login", raise_exception=True
    )(vue)


# Nombre maximum de réservations en attente de déplacement par plan de salle.
MAX_TAMPON = 5


# ─── REPRÉSENTATIONS ────────────────────────────────────────────────────────

@acces_theatre_requis
def representation_list_create(request):
    """
    GET  : affiche la liste des représentations + formulaire de création.
    POST : crée une nouvelle représentation (Create).
    """
    form = RepresentationForm()

    if request.method == 'POST':
        form = RepresentationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Représentation créée avec succès.")
            return redirect('representation_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")

    representations = Representation.objects.all().order_by('date')
    # Ajout du total des inscrits pour chaque représentation
    for rep in representations:
        rep.nb_inscrits = rep.total_reservations()

    return render(request, 'theatre/representations.html', {
        'form': form,
        'representations': representations,
    })


@acces_theatre_requis
def representation_delete(request, pk):
    """Supprime une représentation (Delete)."""
    rep = get_object_or_404(Representation, pk=pk)
    if request.method == 'POST':
        rep.delete()
        messages.success(request, "Représentation supprimée.")
    return redirect('representation_list')


# ─── RÉSERVATIONS ────────────────────────────────────────────────────────────

@acces_theatre_requis
def reservation_create(request, rep_pk):
    """
    GET  : affiche le formulaire de réservation pré-rempli avec la représentation.
    POST : crée la réservation (Create).
    """
    representation = get_object_or_404(Representation, pk=rep_pk)

    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.calculer_prix()
            reservation.save()
            messages.success(request, "Réservation enregistrée avec succès.")
            return redirect('representation_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = ReservationForm(initial={'representation': representation})

    return render(request, 'theatre/reservation_form.html', {
        'form': form,
        'representation': representation,
    })


@acces_theatre_requis
def reservation_list(request):
    """Affiche toutes les réservations (Read)."""
    reservations = Reservation.objects.select_related('representation').all()
    total_places_global = sum(res.nb_adultes + res.nb_enfants for res in reservations)

    return render(request, 'theatre/reservation_list.html', {
        'reservations': reservations,
        'total_places_global': total_places_global,
    })


@acces_theatre_requis
def reservation_edit(request, pk):
    """
    GET  : affiche le formulaire d'édition.
    POST : met à jour la réservation (Update).
    """
    reservation = get_object_or_404(Reservation, pk=pk)

    if request.method == 'POST':
        form = ReservationEditForm(request.POST, instance=reservation)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.calculer_prix()
            reservation.save()
            messages.success(request, "Réservation modifiée avec succès.")
            return redirect('reservation_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs.")
    else:
        form = ReservationEditForm(instance=reservation)

    return render(request, 'theatre/reservation_edit.html', {
        'form': form,
        'reservation': reservation,
    })


@acces_theatre_requis
def reservation_delete(request, pk):
    """Supprime une réservation (Delete)."""
    reservation = get_object_or_404(Reservation, pk=pk)
    if request.method == 'POST':
        reservation.delete()
        messages.success(request, "Réservation supprimée.")
    return redirect('reservation_list')


@acces_theatre_requis
def get_prix(request):
    """API JSON : retourne les prix d'une représentation pour le calcul dynamique."""
    rep_id = request.GET.get('rep_id')
    try:
        rep = Representation.objects.get(pk=rep_id)
        return JsonResponse({
            'prix_adulte': float(rep.prix_adulte),
            'prix_enfant': float(rep.prix_enfant),
        })
    except (Representation.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'error': 'Représentation introuvable'}, status=404)


# ─── PLAN DE SALLE ───────────────────────────────────────────────────────────

@acces_theatre_requis
def plan_salle_generer(request, rep_pk):
    """Génère ou regénère le plan de salle pour une représentation."""
    representation = get_object_or_404(Representation, pk=rep_pk)

    if request.method == 'POST':
        plan = placer_reservations(representation)
        messages.success(request, f"Plan de salle généré : {plan.nb_total_places} places, {plan.nb_rangees} rangées.")
        return redirect('plan_salle_afficher', rep_pk=rep_pk)

    return render(request, 'theatre/plan_salle_confirm.html', {
        'representation': representation,
        'nb_inscrits': representation.total_reservations(),
    })


@acces_theatre_requis
def plan_salle_afficher(request, rep_pk):
    """Affiche le plan de salle avec les réservations placées."""
    representation = get_object_or_404(Representation, pk=rep_pk)
    plan = get_object_or_404(PlanSalle, representation=representation)

    # Construction d'une grille [rangee][colonne] = info_place
    places = PlaceReservee.objects.filter(plan_salle=plan).select_related('reservation')
    grille = {}
    for p in places:
        grille[(p.rangee, p.colonne)] = p

    # Construction ligne par ligne pour le template
    config = plan.configuration
    lignes = []
    for idx_r, nb_cols in enumerate(config):
        rangee = []
        for idx_c in range(nb_cols):
            place = grille.get((idx_r, idx_c))
            rangee.append(place)
        lignes.append(rangee)

    return render(request, 'theatre/plan_salle.html', {
        'representation': representation,
        'plan': plan,
        'lignes': lignes,
        'config': config,
    })
@acces_theatre_requis
def liste_places_imprimer(request, rep_pk):
    """
    Affiche la liste imprimable des places attribuées pour une représentation,
    triée par ordre alphabétique de nom puis prénom.
    """
    representation = get_object_or_404(Representation, pk=rep_pk)
    plan = get_object_or_404(PlanSalle, representation=representation)

    # Récupération des réservations avec leurs places, triées alphabétiquement
    reservations = (
        Reservation.objects
        .filter(representation=representation)
        .prefetch_related('places_attribuees')
        .order_by('nom', 'prenom')
    )

    # Construction de la liste : une ligne par réservation
    lignes = []
    total_general = 0

    for res in reservations:
        numeros = sorted(
            p.numero_place for p in res.places_attribuees.filter(plan_salle=plan)
        )
        lignes.append({
            'nom'        : res.nom,
            'prenom'     : res.prenom,
            'nb_adultes' : res.nb_adultes,
            'nb_enfants' : res.nb_enfants,
            'numeros'    : numeros,
            'prix_total' : res.prix_total,
        })
        total_general += res.prix_total

    return render(request, 'theatre/liste_places_print.html', {
        'representation' : representation,
        'lignes'         : lignes,
        'total_general'  : total_general,
        'nb_reservations': len(lignes),
        'nb_places'      : sum(len(l['numeros']) for l in lignes),
    })

# ─── CONTRÔLE D'ENTRÉE ───────────────────────────────────────────────────────

@acces_theatre_requis
def controle_entree(request, rep_pk):
    """
    Plan de salle interactif complet :
    places réservées + places libres + zone tampon.
    """
    representation = get_object_or_404(Representation, pk=rep_pk)
    plan           = get_object_or_404(PlanSalle, representation=representation)

    config = plan.configuration

    # Places réservées indexées par (rangee, colonne)
    places_res = {
        (p.rangee, p.colonne): p
        for p in PlaceReservee.objects
            .filter(plan_salle=plan)
            .select_related('reservation', 'ticket')
    }

    # Places libres indexées par (rangee, colonne)
    places_lib = {
        (p.rangee, p.colonne): p
        for p in PlaceLibre.objects.filter(plan_salle=plan)
            .select_related('vente_flash')
    }

    # Construction de la grille unifiée
    lignes = []
    for idx_r, nb_cols in enumerate(config):
        rangee = []
        for idx_c in range(nb_cols):
            key = (idx_r, idx_c)
            if key in places_res:
                rangee.append({'type': 'reservee', 'place': places_res[key]})
            elif key in places_lib:
                rangee.append({'type': 'libre', 'place': places_lib[key]})
            else:
                rangee.append({'type': 'vide', 'place': None})
        lignes.append(rangee)

    # Zone tampon
    tampons = ZoneTampon.objects.filter(plan_salle=plan).select_related('reservation')

    return render(request, 'theatre/controle_entree.html', {
        'representation' : representation,
        'plan'           : plan,
        'lignes'         : lignes,
        'tampons'        : tampons,
        'ca_total'       : _calculer_ca(plan),
        'nb_tampon'      : tampons.count(),
        'max_tampon'     : MAX_TAMPON,
    })


@acces_theatre_requis
@require_POST
@transaction.atomic
def valider_entree(request, rep_pk):
    """
    Reçoit la liste des place_ids sélectionnées,
    crée les tickets correspondants et retourne les données pour impression.
    """
    plan           = _plan_verrouille(representation__pk=rep_pk)
    representation = plan.representation

    data = _lire_json(request)
    try:
        place_ids = [int(i) for i in data['place_ids']]
    except (TypeError, KeyError, ValueError):
        return _donnees_invalides()

    if not place_ids:
        return JsonResponse({'erreur': 'Aucune place sélectionnée.'}, status=400)

    places = list(
        PlaceReservee.objects
        .filter(id__in=place_ids, plan_salle=plan)
        .select_related('reservation', 'ticket')
        .order_by('numero_place')
    )

    # Places de chaque réservation concernée, dans l'ordre des numéros : les
    # nb_adultes premières sont au tarif adulte, les suivantes au tarif enfant.
    ordre_places = {}
    for place_id, reservation_id in (
        PlaceReservee.objects
        .filter(plan_salle=plan, reservation_id__in={p.reservation_id for p in places})
        .order_by('numero_place')
        .values_list('id', 'reservation_id')
    ):
        ordre_places.setdefault(reservation_id, []).append(place_id)

    tickets_data = []
    for place in places:
        # Évite les doublons : ne crée pas si ticket valide existant
        if hasattr(place, 'ticket') and place.ticket.statut == 'valide':
            continue

        res        = place.reservation
        est_adulte = ordre_places[res.id].index(place.id) < res.nb_adultes
        prix       = representation.prix_adulte if est_adulte else representation.prix_enfant

        # Création ou réactivation du ticket
        ticket, _ = Ticket.objects.update_or_create(
            place=place,
            defaults={
                'statut'       : 'valide',
                'prix_unitaire': prix,
                'annule_le'    : None,
            }
        )

        tickets_data.append({
            'ticket_id'      : ticket.id,
            'place_id'       : place.id,
            'numero_place'   : place.numero_place,
            'rangee'         : place.rangee + 1,      # affichage 1-based
            'nom'            : res.nom,
            'prenom'         : res.prenom,
            'representation' : representation.nom,
            'date'           : representation.date.strftime('%d/%m/%Y'),
            'prix'           : float(prix),
            'est_adulte'     : est_adulte,
        })

    return JsonResponse({
        'tickets'  : tickets_data,
        'ca_total' : float(_calculer_ca(plan)),
    })


@acces_theatre_requis
@require_POST
@transaction.atomic
def annuler_ticket(request, ticket_id):
    """Annule un ticket — répond en JSON (AJAX) ou redirige (formulaire classique)."""
    ticket = get_object_or_404(Ticket.objects.select_related('place'), pk=ticket_id)
    plan   = _plan_verrouille(pk=ticket.place.plan_salle_id)
    # Relu après le verrou : un autre poste a pu le modifier entre-temps.
    ticket = get_object_or_404(Ticket, pk=ticket_id)

    if ticket.statut == 'valide':
        ticket.statut    = 'annule'
        ticket.annule_le = timezone.now()
        ticket.save()

    # Réponse JSON pour les appels AJAX (controle_entree)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' \
       or request.content_type == 'application/json' \
       or request.headers.get('Accept') == 'application/json':
        return JsonResponse({'succes': True, 'ca_total': float(_calculer_ca(plan))})

    # Redirection pour les formulaires classiques (liste_tickets)
    messages.success(request, "Ticket annulé avec succès.")
    return redirect('liste_tickets', rep_pk=plan.representation_id)


@acces_theatre_requis
def liste_tickets(request, rep_pk):
    """Liste tous les tickets (valides et annulés) pour une représentation."""
    representation = get_object_or_404(Representation, pk=rep_pk)
    plan           = get_object_or_404(PlanSalle, representation=representation)

    tickets = (
        Ticket.objects
        .filter(place__plan_salle=plan)
        .select_related('place__reservation')
        .order_by('place__numero_place')
    )

    ca_total = sum(t.prix_unitaire for t in tickets if t.statut == 'valide')

    return render(request, 'theatre/liste_tickets.html', {
        'representation': representation,
        'tickets'       : tickets,
        'ca_total'      : ca_total,
    })


# ─── VENTE FLASH ────────────────────────────────────────────────────────────

@acces_theatre_requis
@require_POST
@transaction.atomic
def vente_flash(request, plan_pk):
    """
    Enregistre une vente flash sur une place libre.
    Reçoit : place_libre_id, nom, prenom, tarif
    """
    plan = _plan_verrouille(pk=plan_pk)

    data = _lire_json(request)
    try:
        place_libre_id = int(data['place_libre_id'])
        nom            = data['nom'].strip()
        prenom         = data['prenom'].strip()
        tarif          = data['tarif']   # 'adulte' ou 'enfant'
    except (TypeError, KeyError, ValueError, AttributeError):
        return _donnees_invalides()

    if tarif not in ('adulte', 'enfant'):
        return JsonResponse({'erreur': 'Tarif inconnu.'}, status=400)

    if not nom or not prenom:
        return JsonResponse({'erreur': 'Nom et prénom obligatoires.'}, status=400)

    if len(nom) > 100 or len(prenom) > 100:
        return JsonResponse({'erreur': 'Nom ou prénom trop long (100 caractères maximum).'}, status=400)

    place_libre = get_object_or_404(PlaceLibre, pk=place_libre_id, plan_salle=plan)

    if place_libre.statut == 'vendue':
        return JsonResponse({'erreur': 'Cette place est déjà vendue.'}, status=400)

    rep   = plan.representation
    prix  = rep.prix_adulte if tarif == 'adulte' else rep.prix_enfant

    # Une place dont la vente a été annulée garde sa vente flash (statut
    # « annulé ») : on la réutilise, une place ne pouvant avoir qu'une vente.
    vente, _ = VenteFlash.objects.update_or_create(
        place_libre = place_libre,
        defaults    = {
            'nom'      : nom,
            'prenom'   : prenom,
            'tarif'    : tarif,
            'prix'     : prix,
            'statut'   : 'valide',
            'annule_le': None,
            'vendu_le' : timezone.now(),
        },
    )
    place_libre.statut = 'vendue'
    place_libre.save()

    # Recalcul CA
    ca_total = _calculer_ca(plan)

    return JsonResponse({
        'succes'      : True,
        'vente_id'    : vente.id,
        'place_id'    : place_libre.id,
        'numero_place': place_libre.numero_place,
        'rangee'      : place_libre.rangee + 1,
        'nom'         : nom,
        'prenom'      : prenom,
        'tarif'       : tarif,
        'prix'        : float(prix),
        'ca_total'    : float(ca_total),
        # Données pour le ticket
        'ticket_data' : {
            'ticket_id'      : vente.id,
            'place_id'       : place_libre.id,
            'numero_place'   : place_libre.numero_place,
            'rangee'         : place_libre.rangee + 1,
            'nom'            : nom,
            'prenom'         : prenom,
            'representation' : rep.nom,
            'date'           : rep.date.strftime('%d/%m/%Y'),
            'prix'           : float(prix),
            'est_adulte'     : tarif == 'adulte',
            'type'           : 'flash',
        }
    })


@acces_theatre_requis
@require_POST
@transaction.atomic
def annuler_vente_flash(request, vente_id):
    """Annule une vente flash et remet la place en statut libre."""
    vente = get_object_or_404(VenteFlash.objects.select_related('place_libre'), pk=vente_id)
    plan  = _plan_verrouille(pk=vente.place_libre.plan_salle_id)
    vente = get_object_or_404(VenteFlash.objects.select_related('place_libre'), pk=vente_id)

    if vente.statut == 'valide':
        vente.statut    = 'annule'
        vente.annule_le = timezone.now()
        vente.save()

        vente.place_libre.statut = 'libre'
        vente.place_libre.save()

    return JsonResponse({
        'succes'  : True,
        'ca_total': float(_calculer_ca(plan)),
    })


# ─── DÉPLACEMENT DE RÉSERVATION ─────────────────────────────────────────────

@acces_theatre_requis
@require_POST
@transaction.atomic
def mettre_en_tampon(request, plan_pk):
    """
    Déplace une réservation dans la zone tampon :
    libère ses places sur le plan (PlaceReservee → PlaceLibre).
    """
    plan = _plan_verrouille(pk=plan_pk)

    data = _lire_json(request)
    try:
        res_id = int(data['reservation_id'])
    except (TypeError, KeyError, ValueError):
        return _donnees_invalides()

    # Vérification capacité tampon
    if ZoneTampon.objects.filter(plan_salle=plan).count() >= MAX_TAMPON:
        return JsonResponse(
            {'erreur': f'La zone tampon est pleine ({MAX_TAMPON} réservations maximum).'},
            status=400
        )

    reservation = get_object_or_404(Reservation, pk=res_id, representation=plan.representation)

    # Vérifier que la réservation n'est pas déjà en tampon
    if ZoneTampon.objects.filter(plan_salle=plan, reservation=reservation).exists():
        return JsonResponse({'erreur': 'Réservation déjà en zone tampon.'}, status=400)

    # Récupérer les places occupées par cette réservation
    places_res = list(PlaceReservee.objects.filter(plan_salle=plan, reservation=reservation))
    if not places_res:
        return JsonResponse({'erreur': "Cette réservation n'a aucune place sur le plan."}, status=400)

    # Transformer les PlaceReservee en PlaceLibre (leurs tickets éventuels
    # sont supprimés avec elles : on_delete=CASCADE)
    PlaceLibre.objects.bulk_create([
        PlaceLibre(
            plan_salle   = plan,
            numero_place = p.numero_place,
            rangee       = p.rangee,
            colonne      = p.colonne,
            statut       = 'libre',
        )
        for p in places_res
    ])
    PlaceReservee.objects.filter(pk__in=[p.pk for p in places_res]).delete()

    # Créer l'entrée en zone tampon, en notant les places d'origine pour
    # pouvoir les rendre si le déplacement est annulé (retirer_du_tampon)
    tampon = ZoneTampon.objects.create(
        plan_salle     = plan,
        reservation    = reservation,
        places_liberes = [
            {'numero_place': p.numero_place, 'rangee': p.rangee, 'colonne': p.colonne}
            for p in places_res
        ],
    )

    return JsonResponse({
        'succes'    : True,
        'tampon_id' : tampon.id,
        'reservation': {
            'id'        : reservation.id,
            'nom'       : reservation.nom,
            'prenom'    : reservation.prenom,
            'nb_places' : reservation.total_places(),
        },
        'ca_total': float(_calculer_ca(plan)),
    })


@acces_theatre_requis
@require_POST
@transaction.atomic
def placer_depuis_tampon(request, plan_pk):
    """
    Place une réservation depuis la zone tampon sur de nouvelles places.
    Reçoit : tampon_id, place_ids[] (liste de PlaceLibre.id)
    """
    plan = _plan_verrouille(pk=plan_pk)

    data = _lire_json(request)
    try:
        tampon_id = int(data['tampon_id'])
        place_ids = [int(i) for i in data['place_ids']]
    except (TypeError, KeyError, ValueError):
        return _donnees_invalides()

    tampon      = get_object_or_404(ZoneTampon, pk=tampon_id, plan_salle=plan)
    reservation = tampon.reservation
    nb_places   = reservation.total_places()

    if len(place_ids) != nb_places:
        return JsonResponse({
            'erreur': f'Sélectionnez exactement {nb_places} place(s) pour cette réservation.'
        }, status=400)

    places_libres = list(PlaceLibre.objects.filter(
        id__in=place_ids, plan_salle=plan, statut='libre'
    ))
    if len(places_libres) != nb_places:
        return JsonResponse(
            {'erreur': 'Certaines places sélectionnées ne sont plus disponibles.'},
            status=400
        )

    _occuper_places_libres(plan, reservation, places_libres)

    # Retirer du tampon
    tampon.delete()

    # Données de retour pour mise à jour UI
    places_creees = PlaceReservee.objects.filter(
        plan_salle=plan, reservation=reservation
    ).order_by('numero_place')

    return JsonResponse({
        'succes'     : True,
        'reservation': {
            'id'    : reservation.id,
            'nom'   : reservation.nom,
            'prenom': reservation.prenom,
        },
        'nouvelles_places': [
            {
                'place_id'    : p.id,
                'numero_place': p.numero_place,
                'rangee'      : p.rangee,
                'colonne'     : p.colonne,
            }
            for p in places_creees
        ],
        'ca_total': float(_calculer_ca(plan)),
    })


@acces_theatre_requis
@require_POST
@transaction.atomic
def retirer_du_tampon(request, tampon_id):
    """
    Annule le déplacement : la réservation retrouve ses places d'origine,
    à condition qu'elles soient toutes encore libres. Sinon, rien ne change
    et la réservation reste dans le tampon, à placer sur le plan.
    """
    tampon = get_object_or_404(ZoneTampon, pk=tampon_id)
    plan   = _plan_verrouille(pk=tampon.plan_salle_id)
    tampon = get_object_or_404(ZoneTampon, pk=tampon_id)

    # Les tampons créés avant cette version ne notaient que des identifiants
    # de places supprimées : leurs places d'origine sont inconnues.
    origines = tampon.places_liberes
    if not origines or not all(isinstance(p, dict) for p in origines):
        return JsonResponse({
            'erreur': "Les places d'origine de cette réservation ne sont pas connues : "
                      "placez-la sur le plan."
        }, status=400)

    places_libres = list(PlaceLibre.objects.filter(
        plan_salle=plan,
        numero_place__in=[p['numero_place'] for p in origines],
        statut='libre',
    ))
    if len(places_libres) != len(origines):
        return JsonResponse({
            'erreur': "Certaines places d'origine ont été réattribuées entre-temps : "
                      "placez la réservation sur le plan."
        }, status=400)

    _occuper_places_libres(plan, tampon.reservation, places_libres)
    tampon.delete()
    return JsonResponse({'succes': True})


# ─── UTILITAIRES ────────────────────────────────────────────────────────────

def _lire_json(request):
    """Corps JSON d'un appel AJAX, ou None s'il est illisible ou n'est pas un
    objet {...} (les vues répondent alors 400 au lieu d'une erreur 500)."""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _donnees_invalides():
    return JsonResponse({'erreur': 'Données invalides.'}, status=400)


def _plan_verrouille(**filtres):
    """Plan de salle verrouillé jusqu'à la fin de la transaction : deux postes
    (contrôle d'entrée, vente flash, déplacement) qui modifient le même plan
    au même moment passent l'un après l'autre au lieu de vendre ou valider
    deux fois la même place. À appeler dans une vue @transaction.atomic."""
    return get_object_or_404(
        PlanSalle.objects.select_for_update().select_related('representation'), **filtres
    )


def _occuper_places_libres(plan, reservation, places_libres):
    """Attribue des places libres à une réservation (PlaceLibre → PlaceReservee)."""
    PlaceReservee.objects.bulk_create([
        PlaceReservee(
            plan_salle   = plan,
            reservation  = reservation,
            numero_place = p.numero_place,
            rangee       = p.rangee,
            colonne      = p.colonne,
        )
        for p in places_libres
    ])
    PlaceLibre.objects.filter(pk__in=[p.pk for p in places_libres]).delete()


def _calculer_ca(plan):
    """Calcule le CA total (tickets valides + ventes flash valides)."""
    ca_tickets = Ticket.objects.filter(
        place__plan_salle=plan, statut='valide'
    ).aggregate(total=Sum('prix_unitaire'))['total']
    ca_flash = VenteFlash.objects.filter(
        place_libre__plan_salle=plan, statut='valide'
    ).aggregate(total=Sum('prix'))['total']
    return (ca_tickets or Decimal('0')) + (ca_flash or Decimal('0'))
