"""Écran d'inscription d'un membre invité (lien reçu par e-mail)."""
import logging

from django.contrib import messages
from django.contrib.auth import login
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from .forms import InscriptionForm
from .models import InvitationMembre
from .services import creer_membre, nom_complet

logger = logging.getLogger(__name__)


@never_cache
def inscription(request, jeton):
    invitation = InvitationMembre.depuis_jeton(jeton)
    if invitation is None or not invitation.utilisable():
        return render(request, "comptes/invitation_invalide.html", {
            "deja_acceptee": invitation is not None and invitation.statut == InvitationMembre.ACCEPTEE,
        }, status=404 if invitation is None else 410)
    if request.user.is_authenticated:
        messages.info(request, "Vous êtes déjà connecté : déconnectez-vous pour créer un autre compte.")
        return redirect("planning:accueil")

    form = InscriptionForm(request.POST or None, initial={
        "prenom": invitation.prenom, "nom": invitation.nom, "email": invitation.email,
    })
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            # Verrou : un double clic ne crée pas deux comptes
            invitation = InvitationMembre.objects.select_for_update().get(pk=invitation.pk)
            if not invitation.utilisable():
                return render(request, "comptes/invitation_invalide.html", {"deja_acceptee": True}, status=410)
            membre = creer_membre(invitation, d["prenom"].strip(), d["nom"].strip(), d["email"], d["mot_de_passe"])
        login(request, membre, backend="comptes.backends.IdentifiantOuEmailBackend")
        _prevenir_inviteur(invitation, membre)
        messages.success(
            request,
            f"Bienvenue {membre.first_name} ! Votre compte est créé. Pour vous reconnecter, utilisez votre "
            f"adresse e-mail ou votre identifiant « {membre.username} » et votre mot de passe.",
        )
        return redirect("planning:accueil")
    return render(request, "comptes/inscription.html", {"form": form, "invitation": invitation,
                                                        "inviteur": nom_complet(invitation.invite_par)})


def _prevenir_inviteur(invitation, membre):
    inviteur = invitation.invite_par
    if not (inviteur and inviteur.email):
        return
    try:
        send_mail(
            f"{nom_complet(membre)} a rejoint l'espace des membres",
            f"Bonjour,\n\n{nom_complet(membre)} ({membre.email}) a accepté votre invitation et créé son compte "
            f"(identifiant : {membre.username}). Il a les droits d'un membre.\n\n— Site de La Concorde asbl",
            None, [inviteur.email],
        )
    except Exception:
        logger.exception("Invitation : e-mail à l'inviteur non envoyé")
