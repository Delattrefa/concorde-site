"""Envoi des invitations et création du compte d'un nouveau membre."""
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from .models import InvitationMembre


def nom_complet(user):
    if user is None:
        return "L'équipe de La Concorde"
    return user.get_full_name() or user.get_username()


def envoyer_invitation(invitation, jeton):
    """Envoie l'e-mail d'invitation. Laisse passer l'erreur SMTP éventuelle."""
    contexte = {
        "invitation": invitation,
        "lien": InvitationMembre.lien(jeton),
        "inviteur": nom_complet(invitation.invite_par),
        "expire_le": timezone.localtime(invitation.expire_le),
    }
    message = EmailMultiAlternatives(
        "Invitation : rejoignez l'espace des membres de La Concorde",
        render_to_string("comptes/emails/invitation.txt", contexte),
        to=[invitation.email],
        reply_to=[invitation.invite_par.email] if invitation.invite_par and invitation.invite_par.email else None,
    )
    message.attach_alternative(render_to_string("comptes/emails/invitation.html", contexte), "text/html")
    message.send()
    invitation.envoyee_le = timezone.now()
    invitation.save(update_fields=["envoyee_le"])


def identifiant_libre(prenom, nom):
    """Identifiant de connexion « prenom.nom » (sans accents), rendu unique."""
    Membre = get_user_model()
    base = ".".join(p for p in (slugify(prenom), slugify(nom)) if p)[:140] or "membre"
    identifiant, numero = base, 1
    while Membre.objects.filter(username__iexact=identifiant).exists():
        numero += 1
        identifiant = f"{base}{numero}"
    return identifiant


def creer_membre(invitation, prenom, nom, email, mot_de_passe):
    """Compte de simple membre : ni statut équipe, ni groupe, ni permission."""
    membre = get_user_model().objects.create_user(
        identifiant_libre(prenom, nom), email=email, password=mot_de_passe,
        first_name=prenom, last_name=nom, is_staff=False, is_superuser=False,
    )
    invitation.acceptee_le = timezone.now()
    invitation.membre = membre
    invitation.save(update_fields=["acceptee_le", "membre"])
    return membre
