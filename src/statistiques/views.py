"""
Tableau de bord des statistiques de fréquentation (admin Wagtail).
Réservé aux super-utilisateurs et aux groupes ayant reçu la permission
« Peut consulter les statistiques de fréquentation ».
"""
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.template.response import TemplateResponse
from django.utils import timezone

from wagtail.models import Page, Site

from .models import Jour, PageJour, ProvenanceJour

PERIODES = {"7": "7 jours", "30": "30 jours", "90": "3 mois", "365": "12 mois"}
PERIODE_DEFAUT = "30"
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def peut_consulter(user):
    return user.has_perm("statistiques.consulter_statistiques")


def _totaux(debut, fin):
    t = Jour.objects.filter(date__range=(debut, fin)).aggregate(
        vues=Sum("vues"), visiteurs=Sum("visiteurs"), mobiles=Sum("vues_mobiles")
    )
    return {cle: valeur or 0 for cle, valeur in t.items()}


def _evolution(actuel, precedent):
    """Variation en %, ou None si la période précédente est vide."""
    return round((actuel - precedent) * 100 / precedent) if precedent else None


def _serie(debut, fin):
    """Barres du graphique : par jour, ou par mois au-delà de 3 mois."""
    jours = {j.date: j for j in Jour.objects.filter(date__range=(debut, fin))}
    if (fin - debut).days < 90:
        barres = []
        jour = debut
        while jour <= fin:
            j = jours.get(jour)
            barres.append({
                "libelle": f"{jour.day} {MOIS[jour.month - 1]}", "date": jour,
                "visiteurs": j.visiteurs if j else 0, "vues": j.vues if j else 0,
            })
            jour += timedelta(days=1)
    else:
        mois = {}
        for jour, j in jours.items():
            m = mois.setdefault((jour.year, jour.month), {"visiteurs": 0, "vues": 0})
            m["visiteurs"] += j.visiteurs
            m["vues"] += j.vues
        barres = []
        annee, numero = debut.year, debut.month
        while date(annee, numero, 1) <= fin:
            m = mois.get((annee, numero), {"visiteurs": 0, "vues": 0})
            barres.append({"libelle": f"{MOIS[numero - 1]} {annee}", "date": date(annee, numero, 1), **m})
            annee, numero = (annee + 1, 1) if numero == 12 else (annee, numero + 1)
    maximum = max([b["visiteurs"] for b in barres] + [1])
    for i, b in enumerate(barres):
        b["hauteur"] = round(b["visiteurs"] * 100 / maximum, 1)
        b["droite"] = i >= len(barres) / 2  # infobulle alignée à droite
    return barres, maximum


def _titres_des_pages(request):
    """Adresse → titre des pages Wagtail publiées, pour un classement lisible."""
    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first()
    if not site:
        return {}
    racine = site.root_page.url_path
    return {
        "/" + url_path[len(racine):]: titre
        for url_path, titre in Page.objects.live().filter(url_path__startswith=racine).values_list("url_path", "title")
    }


def _classement(requete, champ, nombre):
    lignes = list(requete.values(champ).annotate(total=Sum("vues")).order_by("-total", champ)[:nombre])
    maximum = lignes[0]["total"] if lignes else 1
    for ligne in lignes:
        ligne["part"] = round(ligne["total"] * 100 / maximum, 1)
    return lignes


def tableau(request):
    if not peut_consulter(request.user):
        raise PermissionDenied

    periode = request.GET.get("periode", PERIODE_DEFAUT)
    if periode not in PERIODES:
        periode = PERIODE_DEFAUT
    nb_jours = int(periode)
    fin = timezone.localdate()
    debut = fin - timedelta(days=nb_jours - 1)
    if nb_jours > 90:  # graphique par mois : on part du début du mois
        debut = debut.replace(day=1)
    debut_precedent = debut - (fin - debut) - timedelta(days=1)

    totaux = _totaux(debut, fin)
    precedent = _totaux(debut_precedent, debut - timedelta(days=1))
    barres, maximum = _serie(debut, fin)

    titres = _titres_des_pages(request)
    pages = _classement(PageJour.objects.filter(date__range=(debut, fin)), "chemin", 15)
    for ligne in pages:
        ligne["titre"] = titres.get(ligne["chemin"], "")
    provenances = _classement(ProvenanceJour.objects.filter(date__range=(debut, fin)), "source", 10)

    return TemplateResponse(request, "statistiques/tableau.html", {
        "periodes": PERIODES.items(),
        "periode": periode,
        "debut": debut,
        "fin": fin,
        "totaux": totaux,
        "evolution_visiteurs": _evolution(totaux["visiteurs"], precedent["visiteurs"]),
        "evolution_vues": _evolution(totaux["vues"], precedent["vues"]),
        "pages_par_visite": round(totaux["vues"] / totaux["visiteurs"], 1) if totaux["visiteurs"] else 0,
        "part_mobile": round(totaux["mobiles"] * 100 / totaux["vues"]) if totaux["vues"] else 0,
        "barres": barres,
        "maximum": maximum,
        "par_mois": nb_jours > 90,
        "pages": pages,
        "provenances": provenances,
        "premiere_mesure": Jour.objects.values_list("date", flat=True).first(),
    })
