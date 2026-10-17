"""
Collections de la médiathèque Wagtail propres au calendrier :

    Root
    └── Calendrier
        └── Signature   ← signatures du délégué, utilisées dans les contrats

Les signatures sont des données sensibles :
- dans l'admin Wagtail, seuls les super-utilisateurs voient la collection
  Signature. Wagtail fait hériter les droits d'une collection à ses
  sous-collections : les droits sur les images que les groupes ont sur
  Root ou Calendrier sont donc reportés sur les autres collections ;
- leur fichier original est rangé dans media/contrats_location/signatures/
  (dossier interdit d'accès depuis Internet, voir deploiement/htaccess-
  contrats) sous un nom aléatoire, ce qui rend aussi introuvables les
  adresses de leurs miniatures (dérivées de ce nom).

preparer_collections() remet tout en ordre ; elle est lancée à chaque
déploiement (commande preparer_collections) et ne fait rien si tout est
déjà en place.
"""
import os
import secrets

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from wagtail.images import get_image_model
from wagtail.images.models import Image
from wagtail.models import Collection, GroupCollectionPermission

NOM_COLLECTION_CALENDRIER = "Calendrier"
NOM_COLLECTION_SIGNATURES = "Signature"
DOSSIER_SIGNATURES = "contrats_location/signatures/"


def collection_calendrier():
    racine = Collection.get_first_root_node()
    return racine.get_children().filter(name__iexact=NOM_COLLECTION_CALENDRIER).first()


def collection_signatures():
    """La collection « Calendrier › Signature », ou None si elle n'existe pas."""
    calendrier = collection_calendrier()
    if calendrier is None:
        return None
    return calendrier.get_children().filter(name__iexact=NOM_COLLECTION_SIGNATURES).first()


def _creer_ou_deplacer_collections(rapport):
    racine = Collection.get_first_root_node()
    calendrier = collection_calendrier()
    if calendrier is None:
        calendrier = racine.add_child(name=NOM_COLLECTION_CALENDRIER)
        rapport.append(f"Collection « {NOM_COLLECTION_CALENDRIER} » créée.")

    signature = collection_signatures()
    if signature is None:
        # Une collection « Signature » rangée ailleurs est déplacée (avec ses
        # images) plutôt que dédoublée.
        ailleurs = Collection.objects.filter(name__iexact=NOM_COLLECTION_SIGNATURES).first()
        if ailleurs is not None:
            ailleurs.move(calendrier, pos="sorted-child")
            rapport.append(f"Collection « {ailleurs.name} » déplacée dans « {calendrier.name} ».")
        else:
            calendrier.refresh_from_db()
            calendrier.add_child(name=NOM_COLLECTION_SIGNATURES)
            rapport.append(f"Collection « {NOM_COLLECTION_SIGNATURES} » créée dans « {calendrier.name} ».")
    return collection_calendrier(), collection_signatures()


def _reserver_aux_super_utilisateurs(signature, rapport):
    """Retire aux groupes tout droit sur les images qui couvrirait la
    collection Signature (droit sur elle-même ou sur un de ses parents) et
    le reporte sur les autres branches, pour que les groupes gardent leur
    accès au reste de la médiathèque."""
    # Les droits sur les images portent sur le modèle Image de Wagtail
    # (même avec un modèle d'image personnalisé).
    type_image = ContentType.objects.get_for_model(Image)
    chemin = list(signature.get_ancestors()) + [signature]
    for index, collection in enumerate(chemin):
        droits = GroupCollectionPermission.objects.filter(
            collection=collection, permission__content_type=type_image
        ).select_related("group", "permission")
        if not droits:
            continue
        # Sur Signature elle-même : droit simplement retiré. Sur un parent :
        # reporté sur ses autres sous-collections (pas celle qui mène à
        # Signature).
        suivante = chemin[index + 1] if index + 1 < len(chemin) else None
        branches = [] if suivante is None else collection.get_children().exclude(pk=suivante.pk)
        for droit in droits:
            for branche in branches:
                GroupCollectionPermission.objects.get_or_create(
                    group=droit.group, collection=branche, permission=droit.permission
                )
            rapport.append(
                f"Droit « {droit.permission.codename} » du groupe « {droit.group.name} » "
                f"reporté de « {collection.name} » sur : "
                + (", ".join(b.name for b in branches) or "aucune autre collection") + "."
            )
        droits.delete()


def proteger_fichier_signature(image):
    """Range le fichier original d'une image de signature dans le dossier
    protégé, sous un nom aléatoire, et supprime ses anciennes miniatures
    (elles seront recréées avec un nom introuvable). Renvoie True si le
    fichier a été déplacé."""
    if not image.file or image.file.name.startswith(DOSSIER_SIGNATURES):
        return False
    stockage = image.file.storage
    ancien = image.file.name
    extension = os.path.splitext(ancien)[1].lower()
    with stockage.open(ancien, "rb") as contenu:
        nouveau = stockage.save(f"{DOSSIER_SIGNATURES}{secrets.token_urlsafe(18)}{extension}", contenu)
    get_image_model().objects.filter(pk=image.pk).update(file=nouveau)
    image.file.name = nouveau
    image.renditions.all().delete()
    transaction.on_commit(lambda: stockage.delete(ancien))
    return True


def proteger_fichiers_signatures(signature, rapport):
    for image in get_image_model().objects.filter(collection=signature):
        if proteger_fichier_signature(image):
            rapport.append(f"Fichier de la signature « {image.title} » mis à l'abri.")


@transaction.atomic
def preparer_collections():
    """Crée ou range les collections, réserve Signature aux
    super-utilisateurs et protège ses fichiers. Renvoie la liste des
    changements effectués (vide si tout était déjà en ordre)."""
    rapport = []
    _calendrier, signature = _creer_ou_deplacer_collections(rapport)
    _reserver_aux_super_utilisateurs(signature, rapport)
    proteger_fichiers_signatures(signature, rapport)
    return rapport


def proteger_signature_enregistree(sender, instance, **kwargs):
    """Signal post_save des images : une image ajoutée (ou déplacée) dans
    la collection Signature a aussitôt son fichier mis à l'abri."""
    signature = collection_signatures()
    if signature is not None and instance.collection_id == signature.pk:
        proteger_fichier_signature(instance)
