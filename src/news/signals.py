"""
Une seule actualité « À la une » : à la publication d'une actualité cochée,
la case est retirée des autres, y compris de leur dernière révision (sinon
republier l'ancienne la remettrait à la une sans qu'on l'ait voulu).
"""
from wagtail.signals import page_published

from .models import NewsPage


def une_seule_a_la_une(sender, instance, **kwargs):
    if not instance.a_la_une:
        return
    for autre in NewsPage.objects.filter(a_la_une=True).exclude(pk=instance.pk).select_related("latest_revision"):
        NewsPage.objects.filter(pk=autre.pk).update(a_la_une=False)
        revision = autre.latest_revision
        if revision and revision.content.get("a_la_une"):
            revision.content["a_la_une"] = False
            revision.save(update_fields=["content"])


def activer():
    page_published.connect(une_seule_a_la_une, sender=NewsPage, dispatch_uid="news_une_seule_a_la_une")
