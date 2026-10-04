"""
Modèles de l'application 'calendrier'.

Deux modèles principaux :

- Activite : événement créé par un utilisateur connecté (membre de l'ASBL),
  visible publiquement ou uniquement par les personnes connectées.

- Reservation : demande de location de salle introduite par un visiteur
  non connecté, qui doit être validée ou refusée par un administrateur
  avant d'apparaître comme "réservée" dans le calendrier.

Les deux modèles utilisent une FOURCHETTE DE DATES (date_debut / date_fin)
plutôt qu'une date unique avec horaires : une activité ou une réservation
peut ainsi couvrir un seul jour (date_debut == date_fin) ou plusieurs jours
consécutifs.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse


class Activite(models.Model):
    """Une activité (répétition, spectacle, réunion...) inscrite au calendrier
    par un utilisateur connecté, sur une ou plusieurs journées."""

    # Couleurs par défaut attribuées automatiquement selon la visibilité
    # (utilisées si l'utilisateur n'a pas choisi de couleur personnalisée).
    COULEUR_PUBLIQUE = "#2e7d32"   # vert — visible par tout le monde
    COULEUR_PRIVEE = "#e67e22"     # orange — visible uniquement si connecté

    VISIBILITE_PUBLIQUE = "public"
    VISIBILITE_PRIVEE = "prive"
    VISIBILITE_CHOICES = [
        (VISIBILITE_PUBLIQUE, "Publique (visible par tous les visiteurs)"),
        (VISIBILITE_PRIVEE, "Privée (visible uniquement par les personnes connectées)"),
    ]

    nom = models.CharField("Nom de l'activité", max_length=200)
    description = models.TextField("Description", blank=True)

    date_debut = models.DateField("Date de début")
    date_fin = models.DateField(
        "Date de fin", help_text="Identique à la date de début pour une activité d'un seul jour."
    )

    visibilite = models.CharField(
        "Visibilité",
        max_length=10,
        choices=VISIBILITE_CHOICES,
        default=VISIBILITE_PUBLIQUE,
    )

    # Couleur affichée dans le calendrier (attribuée automatiquement à
    # l'enregistrement selon la visibilité, mais modifiable si besoin).
    couleur = models.CharField(
        "Couleur d'affichage",
        max_length=7,
        blank=True,
        help_text="Code couleur hexadécimal (ex : #2e7d32). Laisser vide pour une "
        "attribution automatique selon la visibilité.",
    )

    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activites",
        verbose_name="Créée par",
    )
    date_creation = models.DateTimeField("Créée le", auto_now_add=True)

    class Meta:
        verbose_name = "Activité"
        verbose_name_plural = "Activités"
        ordering = ["date_debut"]

    def __str__(self):
        if self.date_fin and self.date_fin != self.date_debut:
            return f"{self.nom} — du {self.date_debut:%d/%m/%Y} au {self.date_fin:%d/%m/%Y}"
        return f"{self.nom} — {self.date_debut:%d/%m/%Y}"

    def clean(self):
        """Validation métier : la date de fin ne peut pas être antérieure à
        la date de début."""
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError(
                {"date_fin": "La date de fin ne peut pas être antérieure à la date de début."}
            )

    def save(self, *args, **kwargs):
        # Attribution automatique de la couleur si aucune n'a été choisie,
        # sur base de l'information de visibilité indiquée dans le formulaire.
        if not self.couleur:
            self.couleur = (
                self.COULEUR_PUBLIQUE
                if self.visibilite == self.VISIBILITE_PUBLIQUE
                else self.COULEUR_PRIVEE
            )
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("calendrier:activite_detail", kwargs={"pk": self.pk})

    def est_visible_par(self, user):
        """Renvoie True si l'activité doit être visible pour l'utilisateur
        (anonyme ou connecté) passé en paramètre."""
        if self.visibilite == self.VISIBILITE_PUBLIQUE:
            return True
        return user.is_authenticated

    def peut_etre_modifiee_par(self, user):
        """Seuls l'auteur de l'activité et les administrateurs (staff)
        peuvent la modifier ou la supprimer."""
        return user.is_authenticated and (user.is_staff or self.auteur_id == user.id)


class Reservation(models.Model):
    """Demande de réservation de salle introduite par un visiteur non
    connecté, sur une ou plusieurs journées. Reste 'en attente' jusqu'à
    décision d'un administrateur."""

    STATUT_ATTENTE = "attente"
    STATUT_VALIDEE = "validee"
    STATUT_REFUSEE = "refusee"
    STATUT_CHOICES = [
        (STATUT_ATTENTE, "En attente de traitement"),
        (STATUT_VALIDEE, "Validée"),
        (STATUT_REFUSEE, "Refusée"),
    ]

    # Couleur affichée dans le calendrier une fois la réservation validée.
    COULEUR_RESERVEE = "#7a1f2b"  # bordeaux, cohérent avec la charte du site

    # --- Coordonnées du demandeur (formulaire public, sans connexion) ---
    nom = models.CharField("Nom", max_length=100)
    prenom = models.CharField("Prénom", max_length=100)
    adresse = models.CharField("Adresse complète", max_length=255)
    email = models.EmailField("Adresse e-mail")
    telephone = models.CharField("Téléphone / GSM", max_length=20)

    # --- Détails de la demande ---
    date_debut = models.DateField("Date de début souhaitée")
    date_fin = models.DateField(
        "Date de fin souhaitée",
        help_text="Identique à la date de début pour une réservation d'un seul jour.",
    )
    message = models.TextField("Précisions sur la demande", blank=True)

    # --- Suivi administratif ---
    statut = models.CharField(
        "Statut", max_length=10, choices=STATUT_CHOICES, default=STATUT_ATTENTE
    )
    date_demande = models.DateTimeField("Demande reçue le", auto_now_add=True)
    traite_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_traitees",
        verbose_name="Traitée par",
    )
    date_traitement = models.DateTimeField("Traitée le", null=True, blank=True)

    class Meta:
        verbose_name = "Demande de réservation de salle"
        verbose_name_plural = "Demandes de réservation de salle"
        ordering = ["-date_demande"]

    def __str__(self):
        if self.date_fin and self.date_fin != self.date_debut:
            return (
                f"{self.prenom} {self.nom} — du {self.date_debut:%d/%m/%Y} "
                f"au {self.date_fin:%d/%m/%Y} ({self.get_statut_display()})"
            )
        return f"{self.prenom} {self.nom} — {self.date_debut:%d/%m/%Y} ({self.get_statut_display()})"

    def clean(self):
        if self.date_debut and self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError(
                {"date_fin": "La date de fin ne peut pas être antérieure à la date de début."}
            )

    def get_absolute_url(self):
        return reverse("calendrier:reservation_detail", kwargs={"pk": self.pk})

    @property
    def est_validee(self):
        return self.statut == self.STATUT_VALIDEE


class ContratLocation(models.Model):
    """Contrat de location de salle généré (en PDF) pour une réservation
    validée. Un seul contrat par réservation (régénérer le formulaire
    remplace le document existant)."""

    reservation = models.OneToOneField(
        Reservation,
        on_delete=models.CASCADE,
        related_name="contrat",
        verbose_name="Réservation",
    )

    # --- Personne qui gère la location pour le compte de l'ASBL ----------
    delegue_prenom = models.CharField("Prénom du délégué de l'ASBL", max_length=100)
    delegue_nom = models.CharField("Nom du délégué de l'ASBL", max_length=100)

    # --- Locaux pris en charge par la location (article 1 du contrat) -----
    local_salle = models.BooleanField("Une salle des fêtes et une scène", default=True)
    local_cafe = models.BooleanField("Local dénommé café", default=False)
    local_cuisine = models.BooleanField("Cuisine équipée", default=False)
    local_toilettes = models.BooleanField("Un ensemble sanitaire (toilettes)", default=False)

    # --- Montants (articles 3 et 4 du contrat) -----------------------------
    montant_location = models.DecimalField(
        "Montant de la location (€)", max_digits=8, decimal_places=2
    )
    montant_caution = models.DecimalField(
        "Montant de la caution (€)", max_digits=8, decimal_places=2, default=150
    )

    date_creation = models.DateTimeField("Généré le", auto_now_add=True)
    genere_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contrats_generes",
        verbose_name="Généré par",
    )
    fichier_pdf = models.FileField(
        "Fichier PDF du contrat", upload_to="contrats_location/", blank=True
    )

    # --- Suivi des paiements (page « Suivi des paiements ») ---------------
    # Les montants ci-dessus sont fixés à la génération du contrat ; les
    # champs suivants sont tenus à jour par les administrateurs. Régénérer
    # le contrat ne les modifie pas.
    location_payee = models.BooleanField("Location payée", default=False)
    caution_payee = models.BooleanField("Caution payée", default=False)
    caution_remboursee = models.BooleanField("Caution remboursée", default=False)
    date_paiement = models.DateField("Date du paiement", null=True, blank=True)
    extrait_paiement = models.CharField(
        "N° d'extrait (paiement)", max_length=30, blank=True
    )
    date_remboursement_caution = models.DateField(
        "Date du remboursement de la caution", null=True, blank=True
    )
    extrait_remboursement = models.CharField(
        "N° d'extrait (remboursement)", max_length=30, blank=True
    )

    class Meta:
        verbose_name = "Contrat de location"
        verbose_name_plural = "Contrats de location"

    def __str__(self):
        return f"Contrat — {self.reservation.prenom} {self.reservation.nom}"

    @property
    def fichier_disponible(self):
        """Vrai si le PDF du contrat est enregistré et présent sur le serveur."""
        try:
            return bool(self.fichier_pdf) and self.fichier_pdf.storage.exists(self.fichier_pdf.name)
        except Exception:
            return False

    @property
    def est_solde(self):
        """Location et caution payées, caution remboursée : dossier clôturé."""
        return self.location_payee and self.caution_payee and self.caution_remboursee

    def locaux_selectionnes(self):
        """Liste des libellés des locaux cochés, dans l'ordre attendu par
        le contrat (voir article 1)."""
        libelles = []
        if self.local_salle:
            libelles.append("Une salle des fêtes et une scène")
        if self.local_cafe:
            libelles.append("Local dénommé café")
        if self.local_cuisine:
            libelles.append("Cuisine équipée")
        if self.local_toilettes:
            libelles.append("Un ensemble sanitaire")
        return libelles


# ---------------------------------------------------------------------------
# CONTRAT-TYPE : articles et annexes modifiables par les administrateurs
# ---------------------------------------------------------------------------
class ArticleContrat(models.Model):
    """Article du contrat de location type.

    Le texte est saisi en texte simple, avec quelques conventions de mise
    en forme (voir contrats.AIDE_MISE_EN_FORME) et des variables entre
    accolades, remplacées à la génération par les données de la
    réservation : {date_debut}, {montant_caution}, {locaux}..."""

    ordre = models.PositiveIntegerField(
        "Ordre d'affichage", default=0,
        help_text="Les articles sont imprimés du plus petit au plus grand numéro d'ordre.",
    )
    titre = models.CharField("Titre", max_length=100, help_text="Ex : ARTICLE 5 bis")
    texte = models.TextField("Texte de l'article")
    actif = models.BooleanField(
        "Inclure dans le contrat", default=True,
        help_text="Décocher pour retirer l'article des prochains contrats sans le supprimer.",
    )
    date_modification = models.DateTimeField("Dernière modification", auto_now=True)

    class Meta:
        ordering = ["ordre", "pk"]
        verbose_name = "Article du contrat-type"
        verbose_name_plural = "Articles du contrat-type"

    def __str__(self):
        return self.titre


class AnnexeContrat(models.Model):
    """Annexe (PDF) ajoutée à la suite des articles dans chaque contrat
    généré : inventaire du mobilier, de la vaisselle, conditions
    particulières... Remplaçable à tout moment par un nouveau PDF."""

    ordre = models.PositiveIntegerField(
        "Ordre d'affichage", default=0,
        help_text="Les annexes sont ajoutées au contrat dans cet ordre.",
    )
    titre = models.CharField("Titre", max_length=150, help_text="Ex : Annexe III — Conditions particulières")
    fichier = models.FileField(
        "Fichier PDF",
        upload_to="annexes_contrat/",
        validators=[FileExtensionValidator(["pdf"])],
    )
    actif = models.BooleanField(
        "Joindre au contrat", default=True,
        help_text="Décocher pour ne plus joindre cette annexe aux prochains contrats.",
    )
    date_modification = models.DateTimeField("Dernière modification", auto_now=True)

    class Meta:
        ordering = ["ordre", "pk"]
        verbose_name = "Annexe du contrat-type"
        verbose_name_plural = "Annexes du contrat-type"

    def __str__(self):
        return self.titre
