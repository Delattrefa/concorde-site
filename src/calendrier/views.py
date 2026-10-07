"""
Vues de l'application 'calendrier'.

Organisation (méthode CRUD) :

- Calendrier mensuel  : lecture seule (affichage), pas de modèle direct.
- Activite             : Create, Read (Detail), Update, Delete
                        (+ Read/List via le calendrier lui-même).
- Reservation          : Create (public), Read (Detail/List, admin),
                        Update (traitement : validation/refus, admin),
                        Delete (admin).
"""
from datetime import date, datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q, Sum
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from django.utils.dates import MONTHS, WEEKDAYS
from django.utils import timezone

from .contrats import VARIABLES_DISPONIBLES, AIDE_MISE_EN_FORME, generer_pdf_contrat, nom_fichier_contrat
from .forms import ActiviteForm, AnnexeContratForm, ReservationAdminForm, SuiviPaiementFormSet, ArticleContratForm, ContratLocationForm, ReservationForm
from .models import Activite, AnnexeContrat, ArticleContrat, ContratLocation, Reservation
from .utils import construire_semaines_du_mois, mois_adjacent


def _est_administrateur(user):
    """Fonction de test utilisée par user_passes_test / UserPassesTestMixin :
    seul le personnel (is_staff) peut administrer les réservations."""
    return user.is_authenticated and user.is_staff


# ---------------------------------------------------------------------------
# CALENDRIER MENSUEL (vue principale de l'application)
# ---------------------------------------------------------------------------
class CalendrierMoisView(View):
    """Affiche le calendrier d'un mois donné, avec navigation par mois/année
    (boutons précédent/suivant + listes déroulantes).

    URL sans paramètre  -> mois en cours.
    URL avec annee/mois -> mois demandé.
    """

    template_name = "calendrier/calendrier_mois.html"

    def get(self, request, annee=None, mois=None):
        aujourdhui = date.today()
        annee = annee or aujourdhui.year
        mois = mois or aujourdhui.month

        # Garde-fou : normalise un mois hors bornes (ex: navigation en JS
        # désactivé, ou saisie manuelle d'URL) plutôt que de planter.
        if not 1 <= mois <= 12:
            annee, mois = mois_adjacent(annee, 1, (mois - 1))

        semaines = construire_semaines_du_mois(annee, mois, request.user)

        annee_precedente, mois_precedent = mois_adjacent(annee, mois, -1)
        annee_suivante, mois_suivant = mois_adjacent(annee, mois, +1)

        contexte = {
            "semaines": semaines,
            "annee": annee,
            "mois": mois,
            "nom_mois": MONTHS[mois],
            # Django fournit WEEKDAYS avec 0=lundi ... 6=dimanche
            "jours_semaine": [WEEKDAYS[i] for i in range(7)],
            "annee_precedente": annee_precedente,
            "mois_precedent": mois_precedent,
            "annee_suivante": annee_suivante,
            "mois_suivant": mois_suivant,
            # Pour les listes déroulantes de navigation rapide
            "liste_mois": MONTHS,  # dict {1: "janvier", 2: "février", ...}
            "liste_annees": range(aujourdhui.year - 2, aujourdhui.year + 4),
            "est_administrateur": _est_administrateur(request.user),
            "nb_demandes_en_attente": (
                Reservation.objects.filter(statut=Reservation.STATUT_ATTENTE).count()
                if _est_administrateur(request.user)
                else 0
            ),
        }
        return render(request, self.template_name, contexte)


@require_POST
def aller_a_mois(request):
    """Traite la soumission des listes déroulantes mois/année de navigation
    rapide et redirige vers le mois choisi."""
    try:
        annee = int(request.POST.get("annee"))
        mois = int(request.POST.get("mois"))
    except (TypeError, ValueError):
        messages.error(request, "Mois ou année invalide.")
        return redirect("calendrier:mois_courant")
    return redirect("calendrier:mois", annee=annee, mois=mois)


def jour_action(request, annee, mois, jour):
    """Point d'entrée appelé lors du clic sur une case du calendrier.

    - Administrateur        -> choix : ajouter une activité ou une
                                réservation de salle (date pré-remplie).
    - Utilisateur connecté  -> formulaire d'ajout d'activité (date pré-remplie).
    - Visiteur non connecté -> formulaire de demande de réservation de salle
                                (date pré-remplie).
    """
    try:
        date_cible = date(annee, mois, jour)
    except ValueError:
        raise PermissionDenied("Date invalide.")

    date_str = date_cible.isoformat()

    # Administrateur : choix entre une activité et une réservation de salle.
    if _est_administrateur(request.user):
        return render(request, "calendrier/jour_choix.html", {
            "date_cible": date_cible,
            "url_activite": f"{reverse('calendrier:activite_ajouter')}?date={date_str}",
            "url_reservation": f"{reverse('calendrier:reservation_ajouter')}?date={date_str}",
        })

    if request.user.is_authenticated:
        url = reverse("calendrier:activite_ajouter")
    else:
        url = reverse("calendrier:reservation_demander")
    return redirect(f"{url}?date={date_str}")


# ---------------------------------------------------------------------------
# CRUD — ACTIVITÉS (réservé aux utilisateurs connectés)
# ---------------------------------------------------------------------------
class ActiviteCreateView(LoginRequiredMixin, CreateView):
    """CREATE — Ajout d'une activité. Réservé aux utilisateurs connectés."""

    model = Activite
    form_class = ActiviteForm
    template_name = "calendrier/activite_form.html"
    login_url = "login"

    def get_initial(self):
        """Pré-remplit les dates de début et de fin si une date a été
        transmise depuis le calendrier (clic sur une case du jour) : les
        deux champs sont pré-remplis avec cette même date, l'utilisateur
        peut ensuite étendre la date de fin pour une activité de plusieurs
        jours."""
        initial = super().get_initial()
        date_str = self.request.GET.get("date")
        if date_str:
            try:
                date_cible = datetime.strptime(date_str, "%Y-%m-%d").date()
                initial["date_debut"] = date_cible
                initial["date_fin"] = date_cible
            except ValueError:
                pass
        return initial

    def form_valid(self, form):
        # L'auteur n'est jamais un champ du formulaire : il est déduit de
        # l'utilisateur connecté, pour des raisons de sécurité.
        form.instance.auteur = self.request.user
        messages.success(self.request, "L'activité a bien été ajoutée au calendrier.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "calendrier:mois",
            kwargs={"annee": self.object.date_debut.year, "mois": self.object.date_debut.month},
        )


class ActiviteDetailView(DetailView):
    """READ — Détail d'une activité, avec vérification de la visibilité
    (publique / privée) selon l'utilisateur consultant la page."""

    model = Activite
    template_name = "calendrier/activite_detail.html"
    context_object_name = "activite"

    def get_object(self, queryset=None):
        activite = super().get_object(queryset)
        if not activite.est_visible_par(self.request.user):
            # Une activité privée ne doit jamais fuiter vers un visiteur
            # non connecté, même en devinant l'URL.
            raise PermissionDenied("Cette activité n'est pas accessible.")
        return activite

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["peut_modifier"] = self.object.peut_etre_modifiee_par(self.request.user)
        return contexte


class ActivitePermissionMixin(UserPassesTestMixin):
    """Mixin commun à la modification et à la suppression : seuls l'auteur
    de l'activité et les administrateurs y sont autorisés."""

    raise_exception = True

    def test_func(self):
        activite = self.get_object()
        return activite.peut_etre_modifiee_par(self.request.user)


class ActiviteUpdateView(LoginRequiredMixin, ActivitePermissionMixin, UpdateView):
    """UPDATE — Modification d'une activité existante."""

    model = Activite
    form_class = ActiviteForm
    template_name = "calendrier/activite_form.html"
    login_url = "login"

    def form_valid(self, form):
        messages.success(self.request, "L'activité a bien été modifiée.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "calendrier:mois",
            kwargs={"annee": self.object.date_debut.year, "mois": self.object.date_debut.month},
        )


class ActiviteDeleteView(LoginRequiredMixin, ActivitePermissionMixin, DeleteView):
    """DELETE — Suppression d'une activité."""

    model = Activite
    template_name = "calendrier/activite_confirm_delete.html"
    login_url = "login"
    context_object_name = "activite"

    def get_success_url(self):
        messages.success(self.request, "L'activité a bien été supprimée.")
        return reverse(
            "calendrier:mois",
            kwargs={"annee": self.object.date_debut.year, "mois": self.object.date_debut.month},
        )


# ---------------------------------------------------------------------------
# CRUD — RÉSERVATIONS DE SALLE
# ---------------------------------------------------------------------------
class ReservationCreateView(CreateView):
    """CREATE — Formulaire public de demande de réservation de salle.
    Volontairement accessible sans connexion (voir consignes)."""

    model = Reservation
    form_class = ReservationForm
    template_name = "calendrier/reservation_form.html"

    def get_initial(self):
        """Pré-remplit les dates de début et de fin si une date a été
        transmise depuis le calendrier (clic sur une case du jour)."""
        initial = super().get_initial()
        date_str = self.request.GET.get("date")
        if date_str:
            try:
                date_cible = datetime.strptime(date_str, "%Y-%m-%d").date()
                initial["date_debut"] = date_cible
                initial["date_fin"] = date_cible
            except ValueError:
                pass
        return initial

    def form_valid(self, form):
        messages.success(
            self.request,
            "Votre demande de réservation a bien été envoyée. "
            "Un administrateur l'examinera dans les meilleurs délais.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "calendrier:mois",
            kwargs={"annee": self.object.date_debut.year, "mois": self.object.date_debut.month},
        )


class ReservationAdminCreateView(UserPassesTestMixin, CreateView):
    """CREATE — Réservation de salle encodée directement par un
    administrateur. Validée par défaut : elle apparaît aussitôt comme
    « salle réservée » dans le calendrier, et le contrat peut être rédigé."""

    model = Reservation
    form_class = ReservationAdminForm
    template_name = "calendrier/reservation_form.html"
    raise_exception = True

    def test_func(self):
        return _est_administrateur(self.request.user)

    def get_initial(self):
        initial = super().get_initial()
        initial["statut"] = Reservation.STATUT_VALIDEE
        date_str = self.request.GET.get("date")
        if date_str:
            try:
                date_cible = datetime.strptime(date_str, "%Y-%m-%d").date()
                initial["date_debut"] = date_cible
                initial["date_fin"] = date_cible
            except ValueError:
                pass
        return initial

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["ajout_admin"] = True
        return contexte

    def form_valid(self, form):
        if form.instance.statut != Reservation.STATUT_ATTENTE:
            form.instance.traite_par = self.request.user
            form.instance.date_traitement = timezone.now()
        reponse = super().form_valid(form)
        messages.success(
            self.request,
            f"La réservation de {self.object.prenom} {self.object.nom} a été enregistrée "
            f"({self.object.get_statut_display().lower()}).",
        )
        return reponse

    def get_success_url(self):
        # Page de la réservation : accès direct à la rédaction du contrat.
        return reverse("calendrier:reservation_detail", kwargs={"pk": self.object.pk})


class ReservationUpdateView(UserPassesTestMixin, UpdateView):
    """UPDATE — Modification d'une réservation existante (coordonnées,
    dates, message...), comme pour une activité. Réservé aux
    administrateurs : une réservation est soumise anonymement, il n'y a
    pas d'auteur connecté à qui en confier la modification côté site."""

    model = Reservation
    form_class = ReservationForm
    template_name = "calendrier/reservation_form.html"
    context_object_name = "reservation"
    raise_exception = True

    def test_func(self):
        return _est_administrateur(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "La réservation a bien été modifiée.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("calendrier:reservation_detail", kwargs={"pk": self.object.pk})


class ReservationListView(UserPassesTestMixin, ListView):
    """READ (liste) — Tableau de bord des demandes de réservation.
    Réservé aux administrateurs (is_staff)."""

    model = Reservation
    template_name = "calendrier/reservation_liste.html"
    context_object_name = "reservations"
    paginate_by = 20
    raise_exception = True

    def test_func(self):
        return _est_administrateur(self.request.user)

    def get_queryset(self):
        queryset = super().get_queryset()
        statut = self.request.GET.get("statut")
        if statut in dict(Reservation.STATUT_CHOICES):
            queryset = queryset.filter(statut=statut)
        return queryset

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["statut_filtre"] = self.request.GET.get("statut", "")
        contexte["statut_choices"] = Reservation.STATUT_CHOICES
        return contexte


class ReservationDetailView(UserPassesTestMixin, DetailView):
    """READ (détail) — Coordonnées complètes d'une demande.
    Réservé aux administrateurs : ces données ne doivent jamais être
    visibles par un visiteur ou un membre non-staff."""

    model = Reservation
    template_name = "calendrier/reservation_detail.html"
    context_object_name = "reservation"
    raise_exception = True

    def test_func(self):
        return _est_administrateur(self.request.user)


@user_passes_test(_est_administrateur, login_url="login")
@require_POST
def reservation_traiter(request, pk):
    """UPDATE — Validation ou refus d'une demande de réservation par un
    administrateur. Si validée, la case du calendrier passera au statut
    'salle réservée' pour tous les visiteurs."""
    reservation = get_object_or_404(Reservation, pk=pk)
    action = request.POST.get("action")

    if action == "valider":
        reservation.statut = Reservation.STATUT_VALIDEE
        messages.success(
            request,
            f"La réservation de {reservation.prenom} {reservation.nom} "
            f"pour le {reservation.date_debut:%d/%m/%Y} a été validée.",
        )
    elif action == "refuser":
        reservation.statut = Reservation.STATUT_REFUSEE
        messages.info(
            request,
            f"La réservation de {reservation.prenom} {reservation.nom} a été refusée.",
        )
    elif action == "annuler" and reservation.statut == Reservation.STATUT_VALIDEE:
        # La salle redevient libre ; s'il existe un contrat, il est marqué
        # annulé dans le suivi des paiements (remboursements à y compléter).
        reservation.statut = Reservation.STATUT_ANNULEE
        contrat = getattr(reservation, "contrat", None)
        if contrat is not None and not contrat.annule:
            contrat.annule = True
            contrat.date_annulation = contrat.date_annulation or timezone.localdate()
            contrat.save(update_fields=["annule", "date_annulation"])
            messages.warning(
                request,
                f"La réservation de {reservation.prenom} {reservation.nom} a été annulée. "
                "Si des montants ont été payés, complétez les remboursements dans le suivi des paiements.",
            )
        else:
            messages.info(
                request,
                f"La réservation de {reservation.prenom} {reservation.nom} a été annulée : "
                "la salle est de nouveau libre dans le calendrier.",
            )
    elif action == "retablir" and reservation.statut == Reservation.STATUT_ANNULEE:
        conflit = Reservation.objects.filter(
            statut=Reservation.STATUT_VALIDEE,
            date_debut__lte=reservation.date_fin,
            date_fin__gte=reservation.date_debut,
        ).exclude(pk=reservation.pk).first()
        contrat = getattr(reservation, "contrat", None)
        if conflit:
            messages.error(request, f"Impossible de rétablir : la salle a été réservée entre-temps ({conflit}).")
            return redirect(_url_retour_reservation(request))
        if contrat is not None and (contrat.loyer_rembourse or contrat.caution_rendue_annulation):
            messages.error(
                request,
                "Impossible de rétablir : des remboursements d'annulation ont déjà été enregistrés "
                "dans le suivi des paiements.",
            )
            return redirect(_url_retour_reservation(request))
        reservation.statut = Reservation.STATUT_VALIDEE
        if contrat is not None and contrat.annule:
            contrat.annule = False
            contrat.date_annulation = None
            contrat.extrait_annulation = ""
            contrat.save(update_fields=["annule", "date_annulation", "extrait_annulation"])
        messages.success(request, f"La réservation de {reservation.prenom} {reservation.nom} a été rétablie.")
    else:
        messages.error(request, "Action impossible pour cette réservation.")
        return redirect(_url_retour_reservation(request))

    reservation.traite_par = request.user
    reservation.date_traitement = timezone.now()
    reservation.save()

    return redirect(_url_retour_reservation(request))


def _url_retour_reservation(request):
    """Revient à la page d'où vient l'action (liste ou fiche), par défaut la liste."""
    suivant = request.POST.get("suivant", "")
    if suivant.startswith("/") and not suivant.startswith("//"):
        return suivant
    return reverse("calendrier:reservation_liste")


class ReservationDeleteView(UserPassesTestMixin, DeleteView):
    """DELETE — Suppression définitive d'une demande de réservation
    (archivage manuel). Réservé aux administrateurs."""

    model = Reservation
    template_name = "calendrier/reservation_confirm_delete.html"
    context_object_name = "reservation"
    success_url = reverse_lazy("calendrier:reservation_liste")
    raise_exception = True

    def test_func(self):
        return _est_administrateur(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "La demande de réservation a été supprimée.")
        return super().form_valid(form)


@user_passes_test(_est_administrateur, login_url="login")
def rediger_contrat(request, reservation_pk):
    """Affiche et traite le formulaire de rédaction du contrat de location
    pour une réservation VALIDÉE, puis génère le PDF final (téléchargement
    immédiat + copie conservée sur la fiche de la réservation).

    Réservé aux administrateurs, comme le reste de la gestion des
    réservations. Un contrat déjà généré pour cette réservation est repris
    et modifiable (le nouveau PDF remplace l'ancien à l'enregistrement)."""

    reservation = get_object_or_404(Reservation, pk=reservation_pk)

    if reservation.statut != Reservation.STATUT_VALIDEE:
        messages.error(
            request,
            "Le contrat de location ne peut être rédigé que pour une réservation validée.",
        )
        return redirect("calendrier:reservation_detail", pk=reservation.pk)

    contrat = getattr(reservation, "contrat", None)

    if request.method == "POST":
        form = ContratLocationForm(request.POST, instance=contrat)
        if form.is_valid():
            contrat = form.save(commit=False)
            contrat.reservation = reservation
            contrat.genere_par = request.user

            contenu_pdf = generer_pdf_contrat(reservation, contrat)
            nom_fichier = nom_fichier_contrat(reservation)
            contrat.fichier_pdf.save(nom_fichier, ContentFile(contenu_pdf), save=False)

            contrat.save()

            messages.success(request, "Le contrat de location a bien été généré.")

            # Téléchargement immédiat du PDF généré.
            reponse = HttpResponse(contenu_pdf, content_type="application/pdf")
            reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
            return reponse
    else:
        form = ContratLocationForm(instance=contrat)

    return render(
        request,
        "calendrier/contrat_form.html",
        {"form": form, "reservation": reservation, "contrat": contrat},
    )


@user_passes_test(_est_administrateur, login_url="login")
def telecharger_contrat(request, reservation_pk):
    """Télécharge le PDF du contrat de location d'une réservation.

    Les contrats contiennent des données personnelles : ils ne doivent pas
    être accessibles par une simple URL /media/... L'accès direct au dossier
    media/contrats_location/ est bloqué côté serveur (.htaccess), et seuls
    les administrateurs peuvent les télécharger par cette vue."""

    reservation = get_object_or_404(Reservation, pk=reservation_pk)
    contrat = getattr(reservation, "contrat", None)
    if contrat is None or not contrat.fichier_pdf:
        raise Http404("Aucun contrat pour cette réservation.")

    try:
        fichier = contrat.fichier_pdf.open("rb")
    except FileNotFoundError:
        raise Http404("Le fichier du contrat est introuvable.")

    nom = contrat.fichier_pdf.name.rsplit("/", 1)[-1]
    return FileResponse(fichier, as_attachment=True, filename=nom, content_type="application/pdf")


# ---------------------------------------------------------------------------
# CONTRAT-TYPE : modification des articles et des annexes (administrateurs)
# ---------------------------------------------------------------------------
# Le paramètre ?reservation=<pk> permet de revenir au contrat en cours de
# rédaction après les modifications.

def _reservation_de_retour(request):
    pk = request.GET.get("reservation") or request.POST.get("reservation")
    if pk and str(pk).isdigit():
        return Reservation.objects.filter(pk=pk).first()
    return None


def _url_modele_contrat(request):
    url = reverse("calendrier:modele_contrat")
    reservation = _reservation_de_retour(request)
    return f"{url}?reservation={reservation.pk}" if reservation else url


@user_passes_test(_est_administrateur, login_url="login")
def modele_contrat(request):
    """Vue d'ensemble du contrat-type : articles et annexes."""
    return render(request, "calendrier/modele_contrat.html", {
        "articles": ArticleContrat.objects.all(),
        "annexes": AnnexeContrat.objects.all(),
        "reservation_retour": _reservation_de_retour(request),
    })


@user_passes_test(_est_administrateur, login_url="login")
def apercu_modele_contrat(request):
    """PDF d'exemple du contrat-type avec des données fictives, pour
    vérifier les modifications avant de générer un vrai contrat."""
    from types import SimpleNamespace

    aujourd_hui = timezone.localdate()
    reservation = SimpleNamespace(
        prenom="Prénom", nom="NOM DU LOCATAIRE", adresse="Adresse du locataire",
        telephone="0000 00 00 00", email="locataire@exemple.be",
        date_debut=aujourd_hui, date_fin=aujourd_hui,
    )
    contrat = SimpleNamespace(
        delegue_prenom="Prénom", delegue_nom="NOM DU DÉLÉGUÉ",
        montant_location=0, montant_caution=150,
        locaux_selectionnes=lambda: ["Une salle des fêtes et une scène", "Cuisine équipée"],
    )
    contenu_pdf = generer_pdf_contrat(reservation, contrat)
    reponse = HttpResponse(contenu_pdf, content_type="application/pdf")
    reponse["Content-Disposition"] = 'inline; filename="Apercu contrat-type.pdf"'
    return reponse


class _ContratTypeMixin(UserPassesTestMixin):
    """Accès administrateurs, retour vers la page du contrat-type."""

    raise_exception = True

    def test_func(self):
        return _est_administrateur(self.request.user)

    def get_success_url(self):
        return _url_modele_contrat(self.request)

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["reservation_retour"] = _reservation_de_retour(self.request)
        contexte["url_retour"] = _url_modele_contrat(self.request)
        return contexte


class _ArticleMixin(_ContratTypeMixin):
    model = ArticleContrat
    form_class = ArticleContratForm
    template_name = "calendrier/article_contrat_form.html"

    def get_context_data(self, **kwargs):
        contexte = super().get_context_data(**kwargs)
        contexte["variables"] = VARIABLES_DISPONIBLES
        contexte["aide_mise_en_forme"] = AIDE_MISE_EN_FORME
        return contexte

    def form_valid(self, form):
        messages.success(self.request, f"L'article « {form.instance.titre} » a été enregistré.")
        return super().form_valid(form)


class ArticleContratCreateView(_ArticleMixin, CreateView):
    def get_initial(self):
        dernier = ArticleContrat.objects.order_by("-ordre").first()
        return {"ordre": (dernier.ordre + 10) if dernier else 10}


class ArticleContratUpdateView(_ArticleMixin, UpdateView):
    pass


class ArticleContratDeleteView(_ContratTypeMixin, DeleteView):
    model = ArticleContrat
    template_name = "calendrier/modele_contrat_confirm_delete.html"

    def form_valid(self, form):
        messages.success(self.request, f"L'article « {self.object.titre} » a été supprimé.")
        return super().form_valid(form)


class _AnnexeMixin(_ContratTypeMixin):
    model = AnnexeContrat
    form_class = AnnexeContratForm
    template_name = "calendrier/annexe_contrat_form.html"

    def form_valid(self, form):
        # En cas de remplacement du PDF, supprimer l'ancien fichier.
        ancien_nom = None
        if form.instance.pk and "fichier" in form.changed_data:
            ancien_nom = AnnexeContrat.objects.get(pk=form.instance.pk).fichier.name
        reponse = super().form_valid(form)
        if ancien_nom and ancien_nom != self.object.fichier.name:
            self.object.fichier.storage.delete(ancien_nom)
        messages.success(self.request, f"L'annexe « {self.object.titre} » a été enregistrée.")
        return reponse


class AnnexeContratCreateView(_AnnexeMixin, CreateView):
    def get_initial(self):
        derniere = AnnexeContrat.objects.order_by("-ordre").first()
        return {"ordre": (derniere.ordre + 10) if derniere else 10}


class AnnexeContratUpdateView(_AnnexeMixin, UpdateView):
    pass


class AnnexeContratDeleteView(_ContratTypeMixin, DeleteView):
    model = AnnexeContrat
    template_name = "calendrier/modele_contrat_confirm_delete.html"

    def form_valid(self, form):
        nom_fichier = self.object.fichier.name
        stockage = self.object.fichier.storage
        titre = self.object.titre
        reponse = super().form_valid(form)
        if nom_fichier:
            stockage.delete(nom_fichier)
        messages.success(self.request, f"L'annexe « {titre} » a été supprimée.")
        return reponse


# ---------------------------------------------------------------------------
# SUIVI DES PAIEMENTS : location, caution et remboursement (administrateurs)
# ---------------------------------------------------------------------------
FILTRES_PAIEMENTS = [
    ("", "Toutes les locations"),
    ("a_payer", "Paiement attendu"),
    ("a_rembourser", "Caution à rembourser"),
    ("soldees", "Dossiers clôturés"),
    ("annulees", "Locations annulées"),
]


def _lire_date(valeur):
    """Date AAAA-MM-JJ (champ <input type="date">) ou None si vide/invalide."""
    try:
        return datetime.strptime(valeur, "%Y-%m-%d").date() if valeur else None
    except ValueError:
        return None


def _contrats_recherches(nom, date_du, date_au):
    """Contrats correspondant à la recherche : nom ou prénom du locataire
    (partiel, sans tenir compte des majuscules) et/ou locations qui
    chevauchent la période [date_du, date_au] (bornes facultatives)."""
    contrats = ContratLocation.objects.select_related("reservation")
    for mot in nom.split():
        contrats = contrats.filter(
            Q(reservation__nom__icontains=mot) | Q(reservation__prenom__icontains=mot)
        )
    if date_du:
        contrats = contrats.filter(reservation__date_fin__gte=date_du)
    if date_au:
        contrats = contrats.filter(reservation__date_debut__lte=date_au)
    return contrats


def _filtrer_statut(contrats, filtre):
    if filtre == "a_payer":
        contrats = contrats.filter(annule=False).filter(Q(location_payee=False) | Q(caution_payee=False))
    elif filtre == "a_rembourser":
        contrats = contrats.filter(caution_payee=True, caution_remboursee=False)
    elif filtre == "soldees":
        contrats = contrats.filter(
            Q(annule=False, location_payee=True, caution_payee=True, caution_remboursee=True)
            | Q(annule=True, caution_payee=False)
            | Q(annule=True, caution_remboursee=True)
        )
    elif filtre == "annulees":
        contrats = contrats.filter(annule=True)
    return contrats.order_by("-reservation__date_debut", "-pk")


@user_passes_test(_est_administrateur, login_url="login")
def suivi_paiements(request):
    """Tableau de suivi des paiements des locations de salle : une ligne
    par contrat généré, avec le montant de la location et de la caution
    (repris du contrat) et les informations de paiement à compléter.
    Un seul bouton enregistre toutes les lignes modifiées."""

    filtre = request.GET.get("filtre", "")
    if filtre not in dict(FILTRES_PAIEMENTS):
        filtre = ""

    # --- Recherche : nom et/ou fourchette de dates ------------------------
    nom = request.GET.get("nom", "").strip()
    date_du = _lire_date(request.GET.get("du", ""))
    date_au = _lire_date(request.GET.get("au", ""))
    if date_du and date_au and date_au < date_du:
        date_du, date_au = date_au, date_du
    recherche_active = bool(nom or date_du or date_au)

    selection = _contrats_recherches(nom, date_du, date_au)
    contrats = _filtrer_statut(selection, filtre)

    # Paramètres de recherche conservés dans les liens de filtre
    params_recherche = urlencode({
        cle: valeur for cle, valeur in (
            ("nom", nom),
            ("du", date_du.isoformat() if date_du else ""),
            ("au", date_au.isoformat() if date_au else ""),
        ) if valeur
    })

    if request.method == "POST":
        formset = SuiviPaiementFormSet(request.POST, queryset=contrats)
        if formset.is_valid():
            modifies = formset.save()
            if modifies:
                messages.success(
                    request,
                    f"{len(modifies)} ligne(s) enregistrée(s)."
                    if len(modifies) > 1 else "1 ligne enregistrée.",
                )
            else:
                messages.info(request, "Aucune modification à enregistrer.")
            # On revient sur la même page, avec la même recherche et le même filtre.
            return redirect(request.get_full_path())
        messages.error(request, "Certaines lignes contiennent des erreurs : rien n'a été enregistré.")
    else:
        formset = SuiviPaiementFormSet(queryset=contrats)

    # Totaux : sur la recherche en cours (nom / période), sinon sur tout.
    loyers_payes = selection.filter(location_payee=True).aggregate(t=Sum("montant_location"))["t"] or 0
    loyers_rembourses = selection.filter(annule=True).aggregate(t=Sum("loyer_rembourse"))["t"] or 0
    totaux = {
        # Net des loyers remboursés suite à une annulation
        "locations_encaissees": loyers_payes - loyers_rembourses,
        "locations_attendues": selection.filter(location_payee=False, annule=False).aggregate(t=Sum("montant_location"))["t"] or 0,
        "cautions_detenues": selection.filter(caution_payee=True, caution_remboursee=False).aggregate(t=Sum("montant_caution"))["t"] or 0,
        "loyers_rembourses": loyers_rembourses,
    }

    return render(request, "calendrier/suivi_paiements.html", {
        "formset": formset,
        "filtre": filtre,
        "filtres": FILTRES_PAIEMENTS,
        "totaux": totaux,
        "nom": nom,
        "date_du": date_du,
        "date_au": date_au,
        "recherche_active": recherche_active,
        "params_recherche": params_recherche,
        "nb_resultats": contrats.count(),
    })
