from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render

from wagtail.models import Page
from wagtail.contrib.search_promotions.models import Query


def search(request):
    search_query = request.GET.get("query", "").strip()
    page_number = request.GET.get("page", 1)

    if search_query:
        search_results = Page.objects.live().search(search_query)
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
