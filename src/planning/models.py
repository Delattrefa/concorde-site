"""
Planning interne des membres de l'ASBL (menu Réservations › Planning).
Strictement privé : toutes les pages exigent d'être connecté.

- Evenement : réunion, tâche de l'ASBL ou activité. Une répétition crée
  une occurrence par date, reliées par le même identifiant de série.
- Creneau / Inscription : découpage d'un événement en plages horaires,
  chacune avec un besoin en bénévoles, et les membres inscrits.
- Disponibilite : jours où un membre peut aider.
- Invitation : invitation nominative à un événement, avec réponse.
- Sondage / OptionSondage / Vote : sondage de date (type Doodle) ou de
  décision.
- Canal / Message / Lecture : discussions générales et fil de chaque
  événement.
- Notification / Preferences : alertes dans le site et par e-mail
  (envoyées groupées par la commande planning_taches).
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

MEMBRE = settings.AUTH_USER_MODEL


def est_responsable(user):
    """Responsable du planning : statut équipe ou permission dédiée."""
    return user.is_authenticated and (user.is_staff or user.has_perm("planning.gerer_planning"))


def nom_membre(user):
    if user is None:
        return "Membre supprimé"
    return user.get_full_name() or user.get_username()


class EvenementQuerySet(models.QuerySet):
    def visibles_par(self, user):
        if est_responsable(user):
            return self
        return self.filter(
            Q(reserve_aux_invites=False) | Q(createur=user) | Q(invitations__membre=user)
        ).distinct()


class Evenement(models.Model):
    TYPE_REUNION = "reunion"
    TYPE_TACHE = "tache"
    TYPE_ACTIVITE = "activite"
    TYPES = [
        (TYPE_REUNION, "Réunion"),
        (TYPE_TACHE, "Tâche de l'ASBL"),
        (TYPE_ACTIVITE, "Activité / événement spécial"),
    ]

    type = models.CharField("Type", max_length=10, choices=TYPES, default=TYPE_REUNION)
    titre = models.CharField("Titre", max_length=200)
    description = models.TextField("Description", blank=True)
    lieu = models.CharField("Lieu", max_length=200, blank=True)
    debut = models.DateTimeField("Début")
    fin = models.DateTimeField("Fin")
    serie = models.UUIDField("Série", null=True, blank=True, db_index=True, editable=False)
    reserve_aux_invites = models.BooleanField(
        "Réservé aux invités", default=False,
        help_text="Visible seulement par les invités, son auteur et les responsables (ex. : réunion du CA).",
    )
    annule = models.BooleanField("Annulé", default=False)
    createur = models.ForeignKey(MEMBRE, verbose_name="Créé par", null=True, on_delete=models.SET_NULL,
                                 related_name="evenements_planning")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    objects = EvenementQuerySet.as_manager()

    class Meta:
        verbose_name = "Événement du planning"
        verbose_name_plural = "Événements du planning"
        ordering = ["debut"]
        permissions = [("gerer_planning", "Peut gérer le planning (responsable)")]

    def __str__(self):
        return f"{self.titre} ({timezone.localtime(self.debut):%d/%m/%Y %H:%M})"

    def get_absolute_url(self):
        return reverse("planning:evenement", args=[self.pk])

    def peut_modifier(self, user):
        return est_responsable(user) or (user.is_authenticated and self.createur_id == user.pk)

    def occurrences_suivantes(self):
        """Occurrences de la même série à partir de celle-ci (incluse)."""
        if not self.serie:
            return Evenement.objects.filter(pk=self.pk)
        return Evenement.objects.filter(serie=self.serie, debut__gte=self.debut)

    def participants(self):
        """Membres concernés : auteur, invités (sauf refus) et inscrits."""
        ids = set(self.invitations.exclude(statut=Invitation.REFUSEE).values_list("membre", flat=True))
        ids |= set(Inscription.objects.filter(creneau__evenement=self).values_list("membre", flat=True))
        if self.createur_id:
            ids.add(self.createur_id)
        return ids


class CreneauQuerySet(models.QuerySet):
    def avec_effectif(self):
        # order_by explicite : Meta.ordering est ignoré avec un regroupement
        return self.annotate(nb_inscrits=Count("inscriptions")).order_by("debut", "libelle", "pk")

    def a_combler(self):
        return self.avec_effectif().filter(nb_inscrits__lt=models.F("besoin"), evenement__annule=False)


class Creneau(models.Model):
    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name="creneaux")
    libelle = models.CharField("Poste", max_length=100, blank=True, help_text="Facultatif : bar, caisse, ménage…")
    debut = models.DateTimeField("Début")
    fin = models.DateTimeField("Fin")
    besoin = models.PositiveSmallIntegerField("Bénévoles nécessaires", default=1)
    alerte_envoyee = models.BooleanField(default=False, editable=False)

    objects = CreneauQuerySet.as_manager()

    class Meta:
        verbose_name = "Créneau"
        ordering = ["debut", "libelle"]

    def __str__(self):
        debut, fin = timezone.localtime(self.debut), timezone.localtime(self.fin)
        texte = f"{debut:%d/%m %H:%M}–{fin:%H:%M}"
        return f"{texte} · {self.libelle}" if self.libelle else texte

    def est_urgent(self):
        delai = timedelta(hours=settings.PLANNING_URGENCE_HEURES)
        return timezone.now() < self.debut <= timezone.now() + delai


class Inscription(models.Model):
    creneau = models.ForeignKey(Creneau, on_delete=models.CASCADE, related_name="inscriptions")
    membre = models.ForeignKey(MEMBRE, on_delete=models.CASCADE, related_name="inscriptions_planning")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["creneau", "membre"], name="planning_inscription_unique")]


class Disponibilite(models.Model):
    membre = models.ForeignKey(MEMBRE, on_delete=models.CASCADE, related_name="disponibilites_planning")
    date = models.DateField("Date")
    heure_debut = models.TimeField("À partir de", null=True, blank=True)
    heure_fin = models.TimeField("Jusqu'à", null=True, blank=True)
    note = models.CharField("Remarque", max_length=200, blank=True)

    class Meta:
        verbose_name = "Disponibilité"
        ordering = ["date", "heure_debut"]

    def plage(self):
        if self.heure_debut and self.heure_fin:
            return f"de {self.heure_debut:%H:%M} à {self.heure_fin:%H:%M}"
        if self.heure_debut:
            return f"à partir de {self.heure_debut:%H:%M}"
        if self.heure_fin:
            return f"jusqu'à {self.heure_fin:%H:%M}"
        return "toute la journée"


class Invitation(models.Model):
    EN_ATTENTE = "attente"
    ACCEPTEE = "accepte"
    REFUSEE = "refuse"
    STATUTS = [(EN_ATTENTE, "En attente"), (ACCEPTEE, "Accepté"), (REFUSEE, "Refusé")]

    evenement = models.ForeignKey(Evenement, on_delete=models.CASCADE, related_name="invitations")
    membre = models.ForeignKey(MEMBRE, on_delete=models.CASCADE, related_name="invitations_planning")
    statut = models.CharField("Réponse", max_length=8, choices=STATUTS, default=EN_ATTENTE)
    commentaire = models.CharField("Commentaire", max_length=200, blank=True)
    repondu_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["evenement", "membre"], name="planning_invitation_unique")]


class Sondage(models.Model):
    TYPE_DATE = "date"
    TYPE_DECISION = "decision"
    TYPES = [(TYPE_DATE, "Trouver une date"), (TYPE_DECISION, "Prendre une décision")]

    type = models.CharField("Type de sondage", max_length=10, choices=TYPES, default=TYPE_DATE)
    titre = models.CharField("Question", max_length=200)
    description = models.TextField("Précisions", blank=True)
    choix_multiples = models.BooleanField(
        "Plusieurs choix possibles", default=False,
        help_text="Sondage de décision : chacun peut cocher plusieurs réponses.",
    )
    date_limite = models.DateField("Répondre avant le", null=True, blank=True)
    evenement = models.ForeignKey(Evenement, verbose_name="Événement lié", null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="sondages")
    destinataires = models.ManyToManyField(MEMBRE, blank=True, related_name="sondages_planning_recus",
                                           verbose_name="Destinataires")
    clos = models.BooleanField("Clôturé", default=False)
    createur = models.ForeignKey(MEMBRE, null=True, on_delete=models.SET_NULL, related_name="sondages_planning")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]

    def __str__(self):
        return self.titre

    def get_absolute_url(self):
        return reverse("planning:sondage", args=[self.pk])

    def ouvert(self):
        return not self.clos and not (self.date_limite and self.date_limite < timezone.localdate())

    def peut_modifier(self, user):
        return est_responsable(user) or (user.is_authenticated and self.createur_id == user.pk)

    def visible_par(self, user):
        return (
            est_responsable(user) or self.createur_id == user.pk
            or not self.destinataires.exists() or self.destinataires.filter(pk=user.pk).exists()
        )


class OptionSondage(models.Model):
    sondage = models.ForeignKey(Sondage, on_delete=models.CASCADE, related_name="options")
    libelle = models.CharField("Réponse", max_length=200, blank=True)
    debut = models.DateTimeField(null=True, blank=True)
    fin = models.DateTimeField(null=True, blank=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordre", "debut", "pk"]

    def __str__(self):
        if self.debut:
            debut = timezone.localtime(self.debut)
            texte = f"{debut:%d/%m/%Y}"
            if debut.hour or debut.minute or self.fin:
                texte += f" {debut:%H:%M}"
            if self.fin:
                texte += f"–{timezone.localtime(self.fin):%H:%M}"
            return texte
        return self.libelle


class Vote(models.Model):
    OUI = "oui"
    SI_BESOIN = "si_besoin"
    NON = "non"
    REPONSES = [(OUI, "Oui"), (SI_BESOIN, "Si nécessaire"), (NON, "Non")]

    option = models.ForeignKey(OptionSondage, on_delete=models.CASCADE, related_name="votes")
    membre = models.ForeignKey(MEMBRE, on_delete=models.CASCADE, related_name="votes_planning")
    reponse = models.CharField(max_length=10, choices=REPONSES, default=OUI)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["option", "membre"], name="planning_vote_unique")]


class Canal(models.Model):
    nom = models.CharField("Nom", max_length=100)
    description = models.CharField("Description", max_length=200, blank=True)
    evenement = models.OneToOneField(Evenement, null=True, blank=True, on_delete=models.CASCADE,
                                     related_name="canal")
    archive = models.BooleanField("Archivé", default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Canal de discussion"
        verbose_name_plural = "Canaux de discussion"
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    def get_absolute_url(self):
        if self.evenement_id:
            return reverse("planning:evenement", args=[self.evenement_id]) + "#discussion"
        return reverse("planning:canal", args=[self.pk])

    def visible_par(self, user):
        if self.evenement_id:
            return Evenement.objects.visibles_par(user).filter(pk=self.evenement_id).exists()
        return True


class Message(models.Model):
    canal = models.ForeignKey(Canal, on_delete=models.CASCADE, related_name="messages")
    auteur = models.ForeignKey(MEMBRE, null=True, on_delete=models.SET_NULL, related_name="messages_planning")
    texte = models.TextField("Message", max_length=4000)
    mentions = models.ManyToManyField(MEMBRE, blank=True, related_name="+")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]


class Lecture(models.Model):
    """Dernier message lu par un membre dans un canal."""
    canal = models.ForeignKey(Canal, on_delete=models.CASCADE, related_name="lectures")
    membre = models.ForeignKey(MEMBRE, on_delete=models.CASCADE, related_name="+")
    dernier_message = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["canal", "membre"], name="planning_lecture_unique")]


class Notification(models.Model):
    EVENEMENT = "evenement"
    INVITATION = "invitation"
    SONDAGE = "sondage"
    MESSAGE = "message"
    MENTION = "mention"
    URGENCE = "urgence"
    GENRES = [
        (EVENEMENT, "Événement créé, modifié ou annulé"),
        (INVITATION, "Invitation"),
        (SONDAGE, "Sondage"),
        (MESSAGE, "Nouveau message"),
        (MENTION, "Mention dans une discussion"),
        (URGENCE, "Créneau urgent à combler"),
    ]

    destinataire = models.ForeignKey(MEMBRE, on_delete=models.CASCADE, related_name="notifications_planning")
    genre = models.CharField(max_length=10, choices=GENRES)
    texte = models.CharField(max_length=300)
    lien = models.CharField(max_length=300)
    lue = models.BooleanField(default=False)
    a_envoyer = models.BooleanField("E-mail à envoyer", default=False)
    envoyee_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le", "-pk"]
        indexes = [models.Index(fields=["destinataire", "lue"]), models.Index(fields=["a_envoyer"])]


class Preferences(models.Model):
    MESSAGES_TOUS = "tous"
    MESSAGES_MENTIONS = "mentions"
    MESSAGES_AUCUN = "aucun"

    membre = models.OneToOneField(MEMBRE, on_delete=models.CASCADE, related_name="preferences_planning")
    email_evenements = models.BooleanField("Événements créés, modifiés ou annulés", default=True)
    email_invitations = models.BooleanField("Invitations", default=True)
    email_sondages = models.BooleanField("Nouveaux sondages", default=True)
    email_urgences = models.BooleanField("Créneaux urgents à combler", default=True)
    email_messages = models.CharField(
        "Messages des discussions", max_length=10, default=MESSAGES_MENTIONS,
        choices=[
            (MESSAGES_TOUS, "Tous les messages qui me concernent"),
            (MESSAGES_MENTIONS, "Seulement quand on me mentionne (@)"),
            (MESSAGES_AUCUN, "Aucun"),
        ],
    )

    class Meta:
        verbose_name = "Préférences de notification"

    @classmethod
    def de(cls, user):
        return cls.objects.get_or_create(membre=user)[0]

    def veut_email(self, genre):
        if genre == Notification.MESSAGE:
            return self.email_messages == self.MESSAGES_TOUS
        if genre == Notification.MENTION:
            return self.email_messages != self.MESSAGES_AUCUN
        return {
            Notification.EVENEMENT: self.email_evenements,
            Notification.INVITATION: self.email_invitations,
            Notification.SONDAGE: self.email_sondages,
            Notification.URGENCE: self.email_urgences,
        }.get(genre, False)
