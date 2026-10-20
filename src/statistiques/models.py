"""
Statistiques de fréquentation du site, mesurées par le site lui-même.

Aucun cookie, aucun service extérieur, aucune adresse IP enregistrée : on
ne conserve que des totaux par jour (pages vues, visiteurs, provenance).
Ce type de mesure d'audience est dispensé de consentement (lignes
directrices de la CNIL et de l'Autorité de protection des données).

- Jour : totaux d'une journée.
- PageJour : pages vues d'une adresse, par jour.
- ProvenanceJour : arrivées depuis un autre site (Google, Facebook...).
- SelDuJour / EmpreinteDuJour : comptage des visiteurs distincts. Une
  empreinte est un hachage de l'adresse IP et du navigateur, salé par une
  valeur aléatoire propre à la journée. Sels et empreintes sont effacés
  dès le lendemain : on ne peut plus alors relier deux visites, ni
  retrouver une adresse IP. Conséquence : un visiteur revenu un autre jour
  compte une nouvelle fois.
"""
from django.db import models


class Jour(models.Model):
    date = models.DateField("Date", unique=True)
    vues = models.PositiveIntegerField("Pages vues", default=0)
    visiteurs = models.PositiveIntegerField("Visiteurs", default=0)
    vues_mobiles = models.PositiveIntegerField("Pages vues sur mobile", default=0)

    class Meta:
        verbose_name = "Journée"
        ordering = ["date"]
        permissions = [("consulter_statistiques", "Peut consulter les statistiques de fréquentation")]

    def __str__(self):
        return f"{self.date} : {self.vues} vues"


class PageJour(models.Model):
    date = models.DateField("Date")
    chemin = models.CharField("Adresse", max_length=255)
    vues = models.PositiveIntegerField("Pages vues", default=0)

    class Meta:
        verbose_name = "Page vue par jour"
        constraints = [models.UniqueConstraint(fields=["date", "chemin"], name="statistiques_page_unique")]


class ProvenanceJour(models.Model):
    date = models.DateField("Date")
    source = models.CharField("Site d'origine", max_length=100)
    vues = models.PositiveIntegerField("Arrivées", default=0)

    class Meta:
        verbose_name = "Provenance par jour"
        constraints = [models.UniqueConstraint(fields=["date", "source"], name="statistiques_provenance_unique")]


class SelDuJour(models.Model):
    date = models.DateField(unique=True)
    sel = models.CharField(max_length=64)


class EmpreinteDuJour(models.Model):
    date = models.DateField()
    empreinte = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["date", "empreinte"], name="statistiques_empreinte_unique")]
