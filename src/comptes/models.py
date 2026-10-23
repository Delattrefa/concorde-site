"""
Invitations des nouveaux membres.

Un compte ne se crée que sur invitation d'un super-utilisateur (administration
Django → Invitations de membres). L'invité reçoit un e-mail avec un lien
personnel, à usage unique et limité dans le temps, vers l'écran où il choisit
son nom, son adresse e-mail et son mot de passe. Le compte créé a les seuls
droits d'un membre (ni statut équipe, ni groupe, ni permission).

Seule l'empreinte (SHA-256) du lien est conservée : une copie de la base ne
permet pas d'utiliser une invitation. « Renvoyer » crée un nouveau lien et
rend l'ancien inutilisable.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


def empreinte(jeton):
    return hashlib.sha256(jeton.encode()).hexdigest()


class InvitationMembre(models.Model):
    EN_ATTENTE = "attente"
    ACCEPTEE = "acceptee"
    EXPIREE = "expiree"
    ANNULEE = "annulee"

    email = models.EmailField("Adresse e-mail", help_text="L'e-mail d'invitation part dès l'enregistrement.")
    prenom = models.CharField("Prénom", max_length=150, blank=True)
    nom = models.CharField("Nom", max_length=150, blank=True)
    message = models.TextField(
        "Message personnel", blank=True,
        help_text="Facultatif : ajouté à l'e-mail d'invitation.",
    )
    jeton_hache = models.CharField(max_length=64, unique=True, editable=False)
    invite_par = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Invité par", null=True,
                                   on_delete=models.SET_NULL, related_name="invitations_envoyees", editable=False)
    cree_le = models.DateTimeField("Créée le", auto_now_add=True)
    envoyee_le = models.DateTimeField("Envoyée le", null=True, blank=True, editable=False)
    expire_le = models.DateTimeField("Valable jusqu'au", editable=False)
    acceptee_le = models.DateTimeField("Acceptée le", null=True, blank=True, editable=False)
    membre = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Compte créé", null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="+", editable=False)
    annulee = models.BooleanField("Annulée", default=False, editable=False)

    class Meta:
        verbose_name = "Invitation de membre"
        verbose_name_plural = "Invitations de membres"
        ordering = ["-cree_le"]

    def __str__(self):
        return self.email

    def nouveau_jeton(self):
        """Crée un nouveau lien (l'ancien ne fonctionne plus) et repousse
        l'échéance. Renvoie le jeton en clair, à n'utiliser que dans l'e-mail."""
        jeton = secrets.token_urlsafe(32)
        self.jeton_hache = empreinte(jeton)
        self.expire_le = timezone.now() + timedelta(days=settings.COMPTES_INVITATION_JOURS)
        return jeton

    @classmethod
    def depuis_jeton(cls, jeton):
        return cls.objects.filter(jeton_hache=empreinte(jeton)).first()

    @staticmethod
    def lien(jeton):
        base = settings.WAGTAILADMIN_BASE_URL.rstrip("/")
        return base + reverse("comptes:inscription", args=[jeton])

    @property
    def statut(self):
        if self.acceptee_le:
            return self.ACCEPTEE
        if self.annulee:
            return self.ANNULEE
        if self.expire_le and self.expire_le < timezone.now():
            return self.EXPIREE
        return self.EN_ATTENTE

    def get_statut_display(self):
        return {self.ACCEPTEE: "Acceptée", self.ANNULEE: "Annulée", self.EXPIREE: "Expirée",
                self.EN_ATTENTE: "En attente"}[self.statut]

    def utilisable(self):
        return self.statut == self.EN_ATTENTE
