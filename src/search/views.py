from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render

from wagtail.models import Page
from wagtail.contrib.search_promotions.models import Query


def rechercher_pages(texte):
    """Recherche dans les pages publiées et publiques du site, du plus
    précis au plus tolérant :
    1. pages contenant tous les mots saisis ;
    2. sinon, pages contenant au moins un des mots ;
    3. sinon, titres commençant par le texte saisi (mot incomplet :
       « ducas » trouve « Ducasse d'Hiver »)."""
    pages = Page.objects.live().public()

    resultats = pages.search(texte, operator="and")
    if resultats.count():
        return resultats

    if len(texte.split()) > 1:
        resultats = pages.search(texte, operator="or")
        if resultats.count():
            return resultats

    return pages.autocomplete(texte)


def search(request):
    search_query = request.GET.get("query", "").strip()
    page_number = request.GET.get("page", 1)

    if search_query:
        search_results = rechercher_pages(search_query)
        # Enregistre la requête pour les statistiques / "meilleures réponses"
        Query.get(search_query).add_hit()
    else:
        search_results = Page.objects.none()

    per_page = getattr(settings, "SEARCH_RESULTS_PER_PAGE", 10)
    paginator = Paginator(search_results, per_page)
    try:
        search_results = paginator.page(page_number)
    except PageNotAnInteger:
        search_results = paginator.page(1)
    except EmptyPage:
        search_results = paginator.page(paginator.num_pages)

    return render(
        request,
        "search/search.html",
        {
            "search_query": search_query,
            "search_results": search_results,
        },
    )
