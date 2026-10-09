"""
Newsletter de La Concorde asbl.

- Abonne : les inscrits (formulaire public ou ajout dans l'admin).
- NewsletterPage : page publique d'inscription.
- Newsletter : une lettre rédigée dans l'admin Wagtail (StreamField),
  prévisualisable telle qu'elle sera reçue.
- Envoi / Livraison : file d'attente d'envoi. Lancer un envoi crée une
  livraison par destinataire ; la commande `envoyer_newsletters` (tâche
  cron) les expédie par petits lots pour respecter les limites du serveur
  SMTP d'o2switch. L'envoi reprend là où il s'est arrêté en cas d'erreur.
"""
import uuid

from django.conf import settings
from django.db import models
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from wagtail.admin.panels import FieldPanel, HelpPanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page, PreviewableMixin
from wagtail.search import index
from wagtailseo.models import SeoMixin

from .blocks import CONTENU_NEWSLETTER


# ---------------------------------------------------------------------------
# ABONNÉS
# ---------------------------------------------------------------------------
class Abonne(models.Model):
    STATUT_ACTIF = "actif"
    STATUT_ATTENTE = "attente"
    STATUT_DESINSCRIT = "desinscrit"
    STATUT_CHOICES = [
        (STATUT_ACTIF, "Abonné"),
        (STATUT_ATTENTE, "En attente de confirmation"),
        (STATUT_DESINSCRIT, "Désinscrit"),
    ]

    SOURCE_FORMULAIRE = "formulaire"
    SOURCE_ADMIN = "admin"
    SOURCE_CHOICES = [
        (SOURCE_FORMULAIRE, "Formulaire du site"),
        (SOURCE_ADMIN, "Ajout manuel (admin)"),
    ]

    email = models.EmailField("Adresse e-mail", max_length=254, unique=True)
    prenom = models.CharField("Prénom", max_length=100, blank=True)
    nom = models.CharField("Nom", max_length=100, blank=True)
    statut = models.CharField("Statut", max_length=12, choices=STATUT_CHOICES, default=STATUT_ACTIF)
    source = models.CharField("Origine", max_length=12, choices=SOURCE_CHOICES, default=SOURCE_ADMIN)
    jeton = models.UUIDField(
        "Jeton personnel", default=uuid.uuid4, unique=True, editable=False,
        help_text="Sert aux liens de désinscription et de confirmation.",
    )
    date_inscription = models.DateTimeField("Inscrit le", default=timezone.now)
    date_confirmation = models.DateTimeField("Confirmé le", null=True, blank=True)
    date_desinscription = models.DateTimeField("Désinscrit le", null=True, blank=True)

    panels = [
        FieldPanel("email"),
        FieldPanel("prenom"),
        FieldPanel("nom"),
        FieldPanel("statut"),
        FieldPanel("source"),
    ]

    class Meta:
        verbose_name = "Abonné"
        verbose_name_plural = "Abonnés"
        ordering = ["-date_inscription"]

    def __str__(self):
        nom = f"{self.prenom} {self.nom}".strip()
        return f"{nom} <{self.email}>" if nom else self.email

    def clean(self):
        # Avant le contrôle d'unicité : « Zoe@X.be » et « zoe@x.be » sont la même adresse.
        super().clean()
        self.email = (self.email or "").strip().lower()

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        # Dates tenues à jour quel que soit l'endroit où le statut change
        if self.statut == self.STATUT_DESINSCRIT and not self.date_desinscription:
            self.date_desinscription = timezone.now()
        elif self.statut == self.STATUT_ACTIF:
            self.date_desinscription = None
            if not self.date_confirmation:
                self.date_confirmation = timezone.now()
        super().save(*args, **kwargs)

    def desinscrire(self):
        self.statut = self.STATUT_DESINSCRIT
        self.date_desinscription = timezone.now()
        self.save(update_fields=["statut", "date_desinscription"])

    @property
    def url_desinscription(self):
        return url_absolue(reverse("newsletter:desinscription", args=[self.jeton]))


def url_absolue(chemin):
    """Adresse complète (https://…) d'un chemin du site, pour les e-mails."""
    if not chemin or chemin.startswith(("http://", "https://", "mailto:")):
        return chemin
    base = getattr(settings, "NEWSLETTER_BASE_URL", "") or getattr(settings, "WAGTAILADMIN_BASE_URL", "")
    return base.rstrip("/") + "/" + chemin.lstrip("/")


# ---------------------------------------------------------------------------
# PAGE PUBLIQUE D'INSCRIPTION
# ---------------------------------------------------------------------------
class NewsletterPage(SeoMixin, Page):
    """Page d'inscription à la newsletter, au style de la page d'accueil."""

    max_count = 1
    subpage_types = []

    titre_bandeau = models.CharField(
        "Titre du bandeau", max_length=120, default="Restez informés",
        help_text="Grand titre affiché sur l'image, comme sur la page d'accueil.",
    )
    sous_titre = models.CharField("Sous-titre du bandeau", max_length=255, blank=True)
    image_bandeau = models.ForeignKey(
        "wagtailimages.Image", verbose_name="Image du bandeau", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    intro = RichTextField(
        "Présentation", blank=True,
        features=["bold", "italic", "link", "ul"],
        help_text="Ce que contient la newsletter, sa fréquence…",
    )
    titre_formulaire = models.CharField(
        "Titre du formulaire", max_length=120, default="Inscrivez-vous à notre newsletter",
    )
    texte_consentement = models.CharField(
        "Texte de la case de consentement", max_length=255,
        default="J'accepte de recevoir la newsletter de La Concorde asbl. "
                "Je peux me désinscrire à tout moment.",
    )
    message_succes = models.CharField(
        "Message après inscription", max_length=255,
        default="Merci ! Votre inscription est enregistrée.",
    )
    confirmation_par_email = models.BooleanField(
        "Demander une confirmation par e-mail (double opt-in)",
        default=False,
        help_text="Recommandé : l'inscription n'est active qu'après un clic sur le lien reçu par "
                  "e-mail. Évite les inscriptions d'adresses de tiers et prouve le consentement.",
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [FieldPanel("titre_bandeau"), FieldPanel("sous_titre"), FieldPanel("image_bandeau")],
            heading="Bandeau",
        ),
        FieldPanel("intro"),
        MultiFieldPanel(
            [
                FieldPanel("titre_formulaire"),
                FieldPanel("texte_consentement"),
                FieldPanel("message_succes"),
                FieldPanel("confirmation_par_email"),
            ],
            heading="Formulaire",
        ),
    ]
    promote_panels = SeoMixin.seo_panels

    search_fields = Page.search_fields + [index.SearchField("intro")]

    class Meta:
        verbose_name = "Page d'inscription à la newsletter"

    def serve(self, request, *args, **kwargs):
        # Le traitement du formulaire est dans views.py pour rester lisible.
        from .views import servir_page_inscription

        return servir_page_inscription(self, request, *args, **kwargs)


# ---------------------------------------------------------------------------
# NEWSLETTERS
# ---------------------------------------------------------------------------
class LienEnvoiPanel(HelpPanel):
    """Lien « Envoyer cette newsletter » dans l'éditeur de la newsletter."""

    class BoundPanel(HelpPanel.BoundPanel):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            lettre = self.instance
            if lettre is not None and lettre.pk:
                self.content = format_html(
                    '<p><a class="button" href="{}">✉ Préparer l\'envoi de cette newsletter</a></p>'
                    "<p>Enregistrez d'abord vos modifications. L'étape suivante affiche le nombre de "
                    "destinataires et permet d'envoyer un e-mail de test avant l'envoi réel.</p>",
                    reverse("newsletter_admin:envoyer", args=[lettre.pk]),
                )
            else:
                self.content = format_html(
                    "<p>Enregistrez la newsletter pour pouvoir l'envoyer. "
                    "Utilisez l'aperçu (en haut à droite) pour la voir telle qu'elle sera reçue.</p>"
                )


class Newsletter(PreviewableMixin, models.Model):
    STATUT_BROUILLON = "brouillon"
    STATUT_EN_COURS = "en_cours"
    STATUT_ENVOYEE = "envoyee"
    STATUT_CHOICES = [
        (STATUT_BROUILLON, "Brouillon"),
        (STATUT_EN_COURS, "Envoi en cours"),
        (STATUT_ENVOYEE, "Envoyée"),
    ]

    titre = models.CharField(
        "Titre interne", max_length=150,
        help_text="Pour vous repérer dans l'admin (ex : Newsletter d'octobre 2026).",
    )
    objet = models.CharField(
        "Objet de l'e-mail", max_length=150,
        help_text="Ce que les destinataires voient dans leur boîte de réception. Court et précis.",
    )
    preheader = models.CharField(
        "Texte d'aperçu", max_length=150, blank=True,
        help_text="Phrase affichée après l'objet dans la plupart des messageries.",
    )
    salutation = models.CharField(
        "Formule d'appel", max_length=100, blank=True, default="Bonjour {prenom},",
        help_text="{prenom} est remplacé par le prénom de l'abonné (ou retiré s'il est inconnu). "
                  "Laisser vide pour ne pas en mettre.",
    )
    contenu = StreamField(CONTENU_NEWSLETTER, verbose_name="Contenu", use_json_field=True)
    statut = models.CharField(
        "Statut", max_length=10, choices=STATUT_CHOICES, default=STATUT_BROUILLON, editable=False,
    )
    date_creation = models.DateTimeField("Créée le", auto_now_add=True)
    date_modification = models.DateTimeField("Modifiée le", auto_now=True)
    date_envoi = models.DateTimeField("Envoyée le", null=True, blank=True, editable=False)

    panels = [
        LienEnvoiPanel(heading="Envoi"),
        MultiFieldPanel(
            [FieldPanel("titre"), FieldPanel("objet"), FieldPanel("preheader"), FieldPanel("salutation")],
            heading="En-tête de l'e-mail",
        ),
        FieldPanel("contenu"),
    ]

    class Meta:
        verbose_name = "Newsletter"
        verbose_name_plural = "Newsletters"
        ordering = ["-date_creation"]
        permissions = [("envoyer_newsletter", "Peut envoyer une newsletter aux abonnés")]

    def __str__(self):
        return self.titre

    # --- Aperçu dans l'admin : l'e-mail tel qu'il sera reçu -----------------
    def serve_preview(self, request, mode_name):
        from .rendu import personnaliser, rendre_newsletter

        html, _texte = rendre_newsletter(self)
        prenom = getattr(request.user, "first_name", "") or ""
        html = personnaliser(html, prenom=prenom, url_desinscription="#desinscription")
        return HttpResponse(html)

    def lien_envoi(self):
        return format_html(
            '<a href="{}">{}</a>',
            reverse("newsletter_admin:envoyer", args=[self.pk]),
            "Envoyer…" if self.statut == self.STATUT_BROUILLON else "Suivi de l'envoi",
        )

    lien_envoi.short_description = "Envoi"


class Envoi(models.Model):
    """Un envoi d'une newsletter : la file des destinataires est figée au
    lancement (les abonnés inscrits ensuite ne la reçoivent pas)."""

    STATUT_EN_COURS = "en_cours"
    STATUT_TERMINE = "termine"
    STATUT_ANNULE = "annule"
    STATUT_CHOICES = [
        (STATUT_EN_COURS, "En cours"),
        (STATUT_TERMINE, "Terminé"),
        (STATUT_ANNULE, "Annulé"),
    ]

    newsletter = models.ForeignKey(Newsletter, on_delete=models.CASCADE, related_name="envois")
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default=STATUT_EN_COURS)
    lance_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    date_lancement = models.DateTimeField(default=timezone.now)
    date_fin = models.DateTimeField(null=True, blank=True)
    derniere_erreur = models.TextField(blank=True)

    class Meta:
        verbose_name = "Envoi"
        ordering = ["-date_lancement"]

    def __str__(self):
        return f"{self.newsletter} — {self.date_lancement:%d/%m/%Y %H:%M}"

    def compteurs(self):
        par_statut = {
            ligne["statut"]: ligne["n"]
            for ligne in self.livraisons.order_by().values("statut").annotate(n=models.Count("id"))
        }
        total = sum(par_statut.values())
        return {
            "total": total,
            "envoyes": par_statut.get(Livraison.STATUT_ENVOYE, 0),
            "echecs": par_statut.get(Livraison.STATUT_ECHEC, 0),
            "restants": par_statut.get(Livraison.STATUT_A_ENVOYER, 0),
            "ignores": par_statut.get(Livraison.STATUT_IGNORE, 0),
        }


class Livraison(models.Model):
    STATUT_A_ENVOYER = "a_envoyer"
    STATUT_ENVOYE = "envoye"
    STATUT_ECHEC = "echec"
    STATUT_IGNORE = "ignore"
    STATUT_CHOICES = [
        (STATUT_A_ENVOYER, "À envoyer"),
        (STATUT_ENVOYE, "Envoyé"),
        (STATUT_ECHEC, "Échec"),
        (STATUT_IGNORE, "Non envoyé (désinscrit ou annulé)"),
    ]

    envoi = models.ForeignKey(Envoi, on_delete=models.CASCADE, related_name="livraisons")
    abonne = models.ForeignKey(Abonne, null=True, on_delete=models.SET_NULL, related_name="livraisons")
    email = models.EmailField(max_length=254)
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default=STATUT_A_ENVOYER, db_index=True)
    tentatives = models.PositiveSmallIntegerField(default=0)
    erreur = models.CharField(max_length=255, blank=True)
    date_envoi = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "Livraison"
        constraints = [
            models.UniqueConstraint(fields=["envoi", "email"], name="newsletter_livraison_unique"),
        ]

    def __str__(self):
        return f"{self.email} ({self.get_statut_display()})"
