from django.db import models
from django.core.validators import MinValueValidator


class AccesApplication(models.Model):
    """Modèle technique, sans données propres, servant uniquement à
    déclarer une permission Django dédiée : 'Peut accéder à l'application
    Théâtre'. Cette permission est assignable à des utilisateurs
    spécifiques (ou à un groupe) directement depuis l'admin Django
    standard (/django-admin/auth/user/<id>/change/, section
    'Permissions utilisateur'), sans interface dédiée à écrire.

    Les super-utilisateurs ont toujours accès (comportement natif de
    Django : has_perm() renvoie toujours True pour un super-utilisateur).
    """

    class Meta:
        managed = False  # Aucune table réelle : ce modèle ne stocke rien.
        default_permissions = ()  # Pas de add/change/delete/view générés.
        permissions = [
            ("acces_application", "Peut accéder à l'application Théâtre"),
        ]


class Representation(models.Model):
    """Modèle représentant un spectacle avec date et tarifs."""
    nom = models.CharField(max_length=200, verbose_name="Nom de la représentation")
    date = models.DateField(verbose_name="Date")
    prix_adulte = models.DecimalField(
        max_digits=8, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Prix adulte (€)"
    )
    prix_enfant = models.DecimalField(
        max_digits=8, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Prix enfant (€)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Représentation"
        verbose_name_plural = "Représentations"
        ordering = ['date']

    def __str__(self):
        return f"{self.nom} — {self.date.strftime('%d/%m/%Y')}"

    def total_reservations(self):
        """Retourne le nombre total de places réservées pour cette représentation."""
        reservations = self.reservations.all()
        return sum(r.nb_adultes + r.nb_enfants for r in reservations)


# Choix pour les préférences de placement
RANGEE_PREFEREE_CHOICES = [
    ('', 'Sans préférence'),
    ('1', 'Rangée 1'),
    ('2', 'Rangée 2'),
    ('3', 'Rangée 3'),
    ('4', 'Rangée 4'),
    ('5', 'Rangée 5'),
    ('6', 'Rangée 6'),
]

POSITION_RANGEE = [
    ('', 'Sans préférence'),
    ('avant', 'Avant'),
    ('centre', 'Centre'),
    ('arriere', 'Arrière'),
]

POSITION_COTE = [
    ('', 'Sans préférence'),
    ('gauche', 'Gauche'),
    ('milieu', 'Milieu'),
    ('droite', 'Droite'),
]


class Reservation(models.Model):
    """Modèle représentant une réservation de places."""
    representation = models.ForeignKey(
        Representation, on_delete=models.CASCADE,
        related_name='reservations', verbose_name="Représentation"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    nb_adultes = models.PositiveIntegerField(default=0, verbose_name="Nombre d'adultes")
    nb_enfants = models.PositiveIntegerField(default=0, verbose_name="Nombre d'enfants")
    preference_rangee = models.CharField(
        max_length=10, choices=POSITION_RANGEE, blank=True,
        default='', verbose_name="Préférence rangée"
    )
    preference_cote = models.CharField(
        max_length=10, choices=POSITION_COTE, blank=True,
        default='', verbose_name="Préférence côté"
    )
    rangee_preferee = models.CharField(       # ← nouveau champ
        max_length=1,
        choices=RANGEE_PREFEREE_CHOICES,
        blank=True,
        default='',
        verbose_name="Rangée souhaitée (1-6)"
    )
    remarque = models.TextField(blank=True, null=True, verbose_name="Remarque")
    prix_total = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=0, verbose_name="Prix total (€)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.nom} {self.prenom} — {self.representation}"

    def total_places(self):
        return self.nb_adultes + self.nb_enfants

    def calculer_prix(self):
        """Calcule et sauvegarde le prix total."""
        self.prix_total = (
            self.nb_adultes * self.representation.prix_adulte +
            self.nb_enfants * self.representation.prix_enfant
        )


class PlanSalle(models.Model):
    """Configuration de la salle pour une représentation."""
    representation = models.OneToOneField(
        Representation, on_delete=models.CASCADE,
        related_name='plan_salle', verbose_name="Représentation"
    )
    nb_rangees = models.PositiveIntegerField(verbose_name="Nombre de rangées")
    configuration = models.JSONField(verbose_name="Configuration des rangées (JSON)")
    nb_total_places = models.PositiveIntegerField(verbose_name="Nombre total de places")
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plan de salle"
        verbose_name_plural = "Plans de salle"

    def __str__(self):
        return f"Plan — {self.representation}"


class PlaceReservee(models.Model):
    """Association entre une place numérotée et une réservation."""
    plan_salle = models.ForeignKey(
        PlanSalle, on_delete=models.CASCADE,
        related_name='places', verbose_name="Plan de salle"
    )
    reservation = models.ForeignKey(
        Reservation, on_delete=models.CASCADE,
        related_name='places_attribuees', verbose_name="Réservation"
    )
    numero_place = models.PositiveIntegerField(verbose_name="Numéro de place")
    rangee = models.PositiveIntegerField(verbose_name="Rangée")
    colonne = models.PositiveIntegerField(verbose_name="Colonne")

    class Meta:
        verbose_name = "Place réservée"
        verbose_name_plural = "Places réservées"
        unique_together = ('plan_salle', 'numero_place')
        ordering = ['numero_place']

    def __str__(self):
        return f"Place {self.numero_place} — {self.reservation}"

class Ticket(models.Model):
    """Représente un ticket d'entrée imprimé pour une place donnée."""

    STATUT_CHOICES = [
        ('valide', 'Valide'),
        ('annule', 'Annulé'),
    ]

    place        = models.OneToOneField(
        PlaceReservee, on_delete=models.CASCADE,
        related_name='ticket', verbose_name="Place"
    )
    statut       = models.CharField(
        max_length=10, choices=STATUT_CHOICES,
        default='valide', verbose_name="Statut"
    )
    imprime_le   = models.DateTimeField(auto_now_add=True, verbose_name="Imprimé le")
    annule_le    = models.DateTimeField(null=True, blank=True, verbose_name="Annulé le")
    prix_unitaire = models.DecimalField(
        max_digits=8, decimal_places=2,
        verbose_name="Prix unitaire (€)"
    )

    class Meta:
        verbose_name        = "Ticket"
        verbose_name_plural = "Tickets"
        ordering            = ['place__numero_place']

    def __str__(self):
        return f"Ticket #{self.place.numero_place} — {self.place.reservation}"

    def est_adulte(self):
        """
        Détermine si cette place correspond à un tarif adulte.
        Les premières nb_adultes places de la réservation sont adultes,
        les suivantes sont enfants.
        """
        res = self.place.reservation
        places_res = list(
            PlaceReservee.objects
            .filter(reservation=res, plan_salle=self.place.plan_salle)
            .order_by('numero_place')
            .values_list('id', flat=True)
        )
        idx = places_res.index(self.place.id) if self.place.id in places_res else 0
        return idx < res.nb_adultes
    
class PlaceLibre(models.Model):
    """
    Place non réservée dans le plan de salle.
    Créée lors de la génération du plan pour les places sans réservation.
    """
    plan_salle   = models.ForeignKey(
        PlanSalle, on_delete=models.CASCADE,
        related_name='places_libres', verbose_name="Plan de salle"
    )
    numero_place = models.PositiveIntegerField(verbose_name="Numéro de place")
    rangee       = models.PositiveIntegerField(verbose_name="Rangée")
    colonne      = models.PositiveIntegerField(verbose_name="Colonne")
    statut       = models.CharField(
        max_length=20,
        choices=[
            ('libre',   'Libre'),
            ('vendue',  'Vendue (vente flash)'),
        ],
        default='libre'
    )

    class Meta:
        verbose_name        = "Place libre"
        verbose_name_plural = "Places libres"
        unique_together     = ('plan_salle', 'numero_place')
        ordering            = ['numero_place']

    def __str__(self):
        return f"Place libre #{self.numero_place} — {self.plan_salle}"


class VenteFlash(models.Model):
    """Vente d'une place libre (sans réservation préalable)."""
    place_libre  = models.OneToOneField(
        PlaceLibre, on_delete=models.CASCADE,
        related_name='vente_flash', verbose_name="Place"
    )
    nom          = models.CharField(max_length=100, verbose_name="Nom")
    prenom       = models.CharField(max_length=100, verbose_name="Prénom")
    tarif        = models.CharField(
        max_length=10,
        choices=[('adulte', 'Adulte'), ('enfant', 'Enfant')],
        default='adulte'
    )
    prix         = models.DecimalField(max_digits=8, decimal_places=2)
    vendu_le     = models.DateTimeField(auto_now_add=True)
    statut       = models.CharField(
        max_length=10,
        choices=[('valide', 'Valide'), ('annule', 'Annulé')],
        default='valide'
    )
    annule_le    = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = "Vente flash"
        verbose_name_plural = "Ventes flash"

    def __str__(self):
        return f"Vente flash #{self.place_libre.numero_place} — {self.nom} {self.prenom}"


class ZoneTampon(models.Model):
    """
    Zone tampon : stocke temporairement une réservation déplacée
    en attente de replacement (max 5 entrées par plan).
    """
    plan_salle   = models.ForeignKey(
        PlanSalle, on_delete=models.CASCADE,
        related_name='zone_tampon', verbose_name="Plan de salle"
    )
    reservation  = models.ForeignKey(
        Reservation, on_delete=models.CASCADE,
        related_name='en_tampon', verbose_name="Réservation"
    )
    places_liberes = models.JSONField(
        default=list,
        verbose_name="IDs des PlaceReservee libérées"
    )
    mis_en_tampon_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Zone tampon"
        verbose_name_plural = "Zones tampon"

    def __str__(self):
        return f"Tampon — {self.reservation} ({self.plan_salle})"