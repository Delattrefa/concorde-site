"""
Prépare la base SQLite locale à son export vers MySQL/MariaDB (o2switch).
À lancer AVANT l'export (dumpdata), voir DEPLOIEMENT_O2SWITCH.md.

1. Fusionne les mots-clés qui ne diffèrent que par les majuscules ou les
   accents (« Theatre », « théâtre »…). SQLite les distingue, mais pas
   MySQL (interclassement insensible à la casse et aux accents) : l'import
   échouerait sur ces doublons. Pour chaque groupe, le mot-clé le plus
   utilisé est conservé ; les actualités, images et documents des autres
   lui sont rattachés, y compris dans les versions enregistrées des
   actualités (révisions).
2. Supprime les entrées de l'historique Wagtail qui concernent des pages
   supprimées depuis : elles font échouer l'export.
3. Supprime les redirections créées automatiquement depuis d'anciennes
   adresses accentuées (o2switch ne sert pas ces adresses ; « /médias » et
   « /medias » seraient en outre des doublons pour MySQL).
4. Vérifie qu'aucune autre valeur unique ne devient un doublon pour MySQL
   (majuscules, accents, espaces finaux) : la commande s'arrête en les
   listant, à corriger avant l'export.

Usage : python manage.py preparer_export_mysql [--dry-run]
"""
import unicodedata
from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from wagtail.contrib.redirects.models import Redirect
from taggit.models import Tag, TaggedItemBase
from wagtail.models import Page, PageLogEntry, Revision


def _cle(nom):
    sans_accents = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().split())


def _cle_mysql(valeur):
    """Comparaison de MySQL (interclassement utf8mb4_general_ci) : sans
    majuscules ni accents, espaces finaux ignorés."""
    if not isinstance(valeur, str):
        return valeur
    sans_accents = unicodedata.normalize("NFKD", valeur).encode("ascii", "ignore").decode()
    return sans_accents.lower().rstrip()


def _groupes_uniques(modele):
    """Champs (seuls ou ensemble) soumis à une contrainte d'unicité, dont au
    moins un champ texte."""
    groupes = [(f.name,) for f in modele._meta.local_fields if f.unique and not f.primary_key]
    groupes += [tuple(g) for g in modele._meta.unique_together]
    groupes += [
        tuple(c.fields) for c in modele._meta.constraints
        if isinstance(c, models.UniqueConstraint) and c.fields and c.condition is None
    ]
    texte = (models.CharField, models.TextField)
    return [g for g in groupes if any(isinstance(modele._meta.get_field(n), texte) for n in g)]


def doublons_mysql():
    """Valeurs distinctes pour SQLite mais identiques pour MySQL, dans les
    champs uniques de tous les modèles."""
    resultats = []
    for modele in apps.get_models():
        if not modele._meta.managed or modele._meta.proxy:
            continue
        for champs in _groupes_uniques(modele):
            attributs = [modele._meta.get_field(n).attname for n in champs]
            vus = defaultdict(set)
            for valeurs in modele.objects.values_list(*attributs):
                vus[tuple(_cle_mysql(v) for v in valeurs)].add(valeurs)
            for variantes in vus.values():
                if len(variantes) > 1:
                    resultats.append((modele._meta.label, champs, sorted(variantes, key=str)))
    return resultats


def _modeles_de_liaison():
    """Tables qui relient un mot-clé à un contenu (news.NewsPageTag,
    taggit.TaggedItem pour les images et documents…)."""
    return [
        relation.related_model for relation in Tag._meta.related_objects
        if issubclass(relation.related_model, TaggedItemBase)
    ]


class Command(BaseCommand):
    help = "Prépare la base locale à son export vers MySQL (mots-clés en double, historique orphelin)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Affiche les fusions sans les faire.")

    def handle(self, *args, dry_run=False, **options):
        with transaction.atomic():
            self._fusionner_mots_cles(dry_run)
            orphelines = PageLogEntry.objects.exclude(page_id__in=Page.objects.values("id"))
            nombre = orphelines.count()
            if nombre:
                self.stdout.write(f"{nombre} entrée(s) d'historique de pages supprimées retirée(s).")
                if not dry_run:
                    orphelines.delete()
            accentuees = [r.pk for r in Redirect.objects.filter(automatically_created=True) if not r.old_path.isascii()]
            if accentuees:
                self.stdout.write(f"{len(accentuees)} redirection(s) automatique(s) depuis une adresse accentuée retirée(s).")
                if not dry_run:
                    Redirect.objects.filter(pk__in=accentuees).delete()
            if not dry_run:
                restants = doublons_mysql()
                if restants:
                    for modele, champs, variantes in restants:
                        self.stderr.write(f"  {modele} ({', '.join(champs)}) : " + " / ".join(map(str, variantes)))
                    raise CommandError(
                        "Ces valeurs seraient des doublons pour MySQL (majuscules, accents ou espaces "
                        "finaux) : corrigez-les (par exemple dans l'admin) puis relancez la commande. "
                        "Rien n'a été modifié."
                    )
        if dry_run:
            self.stdout.write("Simulation : rien n'a été modifié.")
        else:
            self.stdout.write(self.style.SUCCESS("Base prête pour l'export."))

    def _fusionner_mots_cles(self, dry_run):
        liaisons = _modeles_de_liaison()

        def utilisations(tag):
            return sum(modele.objects.filter(tag=tag).count() for modele in liaisons)

        groupes = defaultdict(list)
        for tag in Tag.objects.all():
            groupes[_cle(tag.name)].append(tag)
            groupes_slug = _cle(tag.slug)
            if groupes_slug != _cle(tag.name):
                groupes[groupes_slug].append(tag)

        # Regroupement transitif (même nom OU même slug une fois simplifiés)
        fusions, deja = [], set()
        for tags in groupes.values():
            tags = [t for t in {t.pk: t for t in tags}.values() if t.pk not in deja]
            if len(tags) > 1:
                fusions.append(tags)
                deja.update(t.pk for t in tags)

        if not fusions:
            self.stdout.write("Aucun mot-clé en double.")
            return

        for tags in fusions:
            tags.sort(key=lambda t: (-utilisations(t), t.pk))
            garde, doublons = tags[0], tags[1:]
            self.stdout.write(
                f"« {garde.name} » garde : " + ", ".join(f"« {t.name} »" for t in doublons) + " fusionné(s)."
            )
            if dry_run:
                continue
            correspondance = {t.pk: garde.pk for t in doublons}
            for modele in liaisons:
                for lien in modele.objects.filter(tag__in=doublons):
                    # Même contenu (actualité, ou type + numéro pour les images)
                    filtre = {"tag": garde}
                    for champ in ("content_object_id", "content_type_id", "object_id"):
                        if hasattr(lien, champ):
                            filtre[champ] = getattr(lien, champ)
                    if modele.objects.filter(**filtre).exists():
                        lien.delete()  # le contenu avait déjà le mot-clé gardé
                    else:
                        lien.tag = garde
                        lien.save(update_fields=["tag"])
            self._corriger_revisions(correspondance)
            Tag.objects.filter(pk__in=correspondance).delete()

    def _corriger_revisions(self, correspondance):
        """Les révisions des actualités gardent les numéros des mots-clés :
        on remplace ceux des doublons supprimés, sans créer de doublon."""
        for revision in Revision.objects.filter(content__has_key="tagged_items"):
            liens = revision.content.get("tagged_items") or []
            if not any(lien.get("tag") in correspondance for lien in liens):
                continue
            vus, nouveaux = set(), []
            for lien in liens:
                lien["tag"] = correspondance.get(lien.get("tag"), lien.get("tag"))
                if lien["tag"] not in vus:
                    vus.add(lien["tag"])
                    nouveaux.append(lien)
            revision.content["tagged_items"] = nouveaux
            revision.save(update_fields=["content"])
