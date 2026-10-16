"""
Captures d'écran du manuel, prises sur le serveur de démonstration lancé
par preparer.sh (http://127.0.0.1:8765).

Usage :
    python captures.py              # toutes les captures
    python captures.py accueil ...  # seulement celles nommées

Les captures brutes (PNG) vont dans .travail/captures/, puis sont
converties en JPEG optimisés dans docs/manuel/img/ (référencés par
manuel.html).
"""
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

from PIL import Image
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8765"
MANUEL = Path(__file__).resolve().parent.parent
TRAVAIL = MANUEL / ".travail"
BRUT = TRAVAIL / "captures"
IMG = MANUEL / "img"
MOT_DE_PASSE = "Manuel2026!"
ONLY = set(sys.argv[1:])
IDS = json.loads((TRAVAIL / "ids.json").read_text())

BRUT.mkdir(parents=True, exist_ok=True)
IMG.mkdir(exist_ok=True)


def voulu(nom):
    return not ONLY or nom in ONLY


def shot(page, nom, url=None, hauteur=None, avant=None):
    """Capture la page (url relative) ; `hauteur` limite une capture pleine
    page à ses N premiers pixels ; `avant` est appelé avant la capture."""
    if not voulu(nom):
        return
    if url:
        page.goto(BASE + quote(url, safe="/?=&%#"), wait_until="networkidle")
    if avant:
        avant(page)
    page.wait_for_timeout(700)
    chemin = BRUT / f"{nom}.png"
    if hauteur:
        page.screenshot(path=chemin, full_page=True,
                        clip={"x": 0, "y": 0, "width": page.viewport_size["width"], "height": hauteur})
    else:
        page.screenshot(path=chemin)
    print("ok", nom)


def connecter(ctx, utilisateur):
    page = ctx.new_page()
    page.goto(BASE + "/connexion/")
    page.fill("input[name=username]", utilisateur)
    page.fill("input[name=password]", MOT_DE_PASSE)
    page.click('button:has-text("Se connecter")')
    page.wait_for_load_state("networkidle")
    return page


def accepter_cookies(page):
    page.goto(BASE + "/")
    bouton = page.locator('[data-cookies-action="accepter"]')
    if bouton.is_visible():
        bouton.click()


def defiler(y):
    def f(page):
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(1200)
    return f


def survol(selecteur):
    def f(page):
        page.hover(selecteur)
        page.wait_for_timeout(400)
    return f


def ouvrir_visionneuse(page):
    page.locator(".galerie__grille button.galerie-element:not(.galerie-element--video)").first.click()
    page.wait_for_timeout(800)


def vers_photos(page):
    page.evaluate("document.querySelector('#titre-photos').scrollIntoView()")
    page.wait_for_timeout(1500)
    page.evaluate("window.scrollBy(0, -120)")
    page.wait_for_timeout(1200)


def rediger_contrat(page):
    """Remplit le contrat de la demande validée, capture le formulaire,
    puis l'enregistre (le PDF est généré et téléchargé)."""
    page.goto(f"{BASE}/calendrier/reservation/{IDS['demande_validee']}/contrat/", wait_until="networkidle")
    page.fill("input[name=delegue_prenom]", "Marie")
    page.fill("input[name=delegue_nom]", "Dupont")
    for nom in ("local_cafe", "local_cuisine", "local_toilettes"):
        page.check(f"input[name={nom}]")
    page.fill("input[name=montant_location]", "350")
    page.fill("input[name=montant_caution]", "250")
    shot(page, "admin_contrat_form", hauteur=1600)
    with page.expect_download(timeout=30000) as telechargement:
        page.locator('form button[type=submit]').last.click()
    pdf = TRAVAIL / "contrat_exemple.pdf"
    telechargement.value.save_as(pdf)
    # Les deux premières pages du contrat, en image.
    subprocess.run(["pdftoppm", "-r", "80", "-png", "-f", "1", "-l", "2", str(pdf), str(BRUT / "contrat_pdf")], check=True)
    print("ok contrat_pdf")


with sync_playwright() as p:
    nav = p.chromium.launch(channel="chrome")
    options = dict(viewport={"width": 1280, "height": 800}, device_scale_factor=1.5, locale="fr-BE")
    album = IDS["album_photos_url"]

    # ---------------- Visiteur anonyme ----------------
    ctx = nav.new_context(**options)
    page = ctx.new_page()
    shot(page, "cookies", "/")
    accepter_cookies(page)
    shot(page, "accueil", "/")
    shot(page, "accueil_sections", "/", avant=defiler(900))
    shot(page, "accueil_activites", "/", avant=defiler(1700))
    shot(page, "pied_de_page", "/", avant=defiler(99999))
    shot(page, "actualites", "/news/", hauteur=1500)
    shot(page, "actualite_detail", IDS["actualite_url"], hauteur=1400)
    shot(page, "medias", "/medias/", hauteur=1300)
    shot(page, "lightbox", album, avant=ouvrir_visionneuse)
    shot(page, "calendrier_public", "/calendrier/2026/11/", hauteur=1300)
    shot(page, "demande_reservation", "/calendrier/reservation/demander/?date=2026-11-14", hauteur=1500)
    shot(page, "contact", "/contact/", hauteur=1400)
    shot(page, "info", "/info/", hauteur=1300)
    shot(page, "newsletter_inscription", "/newsletter/", hauteur=1000)
    shot(page, "recherche", "/recherche/?query=Noël", hauteur=1100)
    shot(page, "connexion", "/connexion/")
    shot(page, "page_libre", "/le-ble-qui-leve/", hauteur=1300)
    ctx.close()

    # ---------------- Smartphone ----------------
    mobile = nav.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                             locale="fr-BE", is_mobile=True, has_touch=True)
    page = mobile.new_page()
    accepter_cookies(page)
    shot(page, "mobile_accueil", "/")
    shot(page, "mobile_menu", "/", avant=lambda pg: (pg.click(".nav-toggle"), pg.wait_for_timeout(500)))
    shot(page, "mobile_calendrier", "/calendrier/2026/11/")
    mobile.close()

    # ---------------- Membre connecté ----------------
    ctx = nav.new_context(**options)
    page = connecter(ctx, "membre")
    accepter_cookies(page)
    shot(page, "membre_menu_theatre", "/", avant=survol("text=Théâtre"))
    shot(page, "membre_calendrier", "/calendrier/2026/12/", hauteur=1300)
    shot(page, "membre_ajout_activite", "/calendrier/activite/ajouter/?date=2026-11-14", hauteur=1400)
    if IDS["activite_privee"]:
        shot(page, "membre_activite_detail", f"/calendrier/activite/{IDS['activite_privee']}/", hauteur=900)
    shot(page, "membre_ajout_actualite", "/ajouter-actualite/", hauteur=1600)
    shot(page, "membre_actualites", "/news/", hauteur=900)
    ctx.close()

    # ---------------- Administrateur ----------------
    ctx = nav.new_context(**options, accept_downloads=True)
    page = connecter(ctx, "secretariat")
    accepter_cookies(page)
    rep, rep2 = IDS["representation"], IDS["representation_2"]

    # Calendrier et location de salle
    shot(page, "admin_calendrier", "/calendrier/2026/11/", hauteur=1300)
    shot(page, "admin_jour_choix", "/calendrier/2026/11/15/", hauteur=900)
    shot(page, "admin_reservations", "/calendrier/reservations/", hauteur=1400)
    shot(page, "admin_reservation_attente", f"/calendrier/reservation/{IDS['demande_attente']}/", hauteur=1300)
    if voulu("admin_contrat_form") or voulu("contrat_pdf"):
        rediger_contrat(page)
    shot(page, "admin_reservation_validee", f"/calendrier/reservation/{IDS['demande_validee']}/", hauteur=1400)
    shot(page, "admin_paiements", "/calendrier/reservation/paiements/", hauteur=1100)
    shot(page, "admin_contrat_type", "/calendrier/contrat-type/", hauteur=1500)
    shot(page, "admin_mise_en_page", "/calendrier/contrat-type/mise-en-page/", hauteur=1300)

    # Médias
    shot(page, "album", album, hauteur=1500)
    shot(page, "album_photos", album, avant=vers_photos)
    shot(page, "admin_ajout_photos", f"/galerie/{IDS['album_photos']}/ajouter-photos/", hauteur=1100)
    shot(page, "admin_ajout_video", f"/galerie/{IDS['album_photos']}/ajouter-video/", hauteur=1100)

    # Théâtre
    shot(page, "theatre_representations", "/theatre/", hauteur=1300)
    shot(page, "theatre_reservation_form", f"/theatre/reservation/nouvelle/{rep2}/", hauteur=1300)
    shot(page, "theatre_reservations", "/theatre/reservations/", hauteur=1300)
    shot(page, "theatre_plan_confirm", f"/theatre/plan/{rep}/generer/", hauteur=800)
    shot(page, "theatre_plan", f"/theatre/plan/{rep}/", hauteur=1700)
    shot(page, "theatre_imprimer", f"/theatre/plan/{rep}/imprimer/", hauteur=1300)
    shot(page, "theatre_entree", f"/theatre/entree/{rep}/", hauteur=1300)
    shot(page, "theatre_tickets", f"/theatre/entree/{rep}/tickets/", hauteur=1100)

    # Administration Wagtail
    accueil, actu, nl = IDS["accueil"], IDS["actualite"], IDS["newsletter"]
    shot(page, "wagtail_tableau_de_bord", "/admin/")
    shot(page, "wagtail_pages", f"/admin/pages/{accueil}/", hauteur=1100)
    shot(page, "wagtail_edit_accueil", f"/admin/pages/{accueil}/edit/", hauteur=1500)
    shot(page, "wagtail_edit_actualite", f"/admin/pages/{actu}/edit/", hauteur=1400)
    shot(page, "wagtail_edit_album", f"/admin/pages/{IDS['album_photos']}/edit/", hauteur=1400)
    shot(page, "wagtail_ajout_page", f"/admin/pages/{accueil}/add_subpage/", hauteur=1000)
    shot(page, "wagtail_images", "/admin/images/", hauteur=1000)
    shot(page, "wagtail_menu_edit", f"/admin/snippets/navigation/mainmenu/edit/{IDS['menu']}/", hauteur=1500)
    shot(page, "wagtail_formulaires", "/admin/forms/", hauteur=800)
    shot(page, "wagtail_menu", "/admin/snippets/navigation/mainmenu/", hauteur=900)
    shot(page, "wagtail_parametres", "/admin/settings/navigation/socialsettings/", hauteur=1200)
    shot(page, "wagtail_newsletters", "/admin/snippets/newsletter/newsletter/", hauteur=800)
    shot(page, "wagtail_newsletter_edit", f"/admin/snippets/newsletter/newsletter/edit/{nl}/", hauteur=1500)
    shot(page, "wagtail_newsletter_envoyer", f"/admin/newsletter/{nl}/envoyer/", hauteur=1200)
    shot(page, "wagtail_abonnes", "/admin/snippets/newsletter/abonne/", hauteur=900)
    shot(page, "wagtail_seo", f"/admin/pages/{actu}/edit/#tab-promotion", hauteur=1300)

    # Administration Django
    shot(page, "django_admin", "/django-admin/", hauteur=1200)
    shot(page, "django_user", f"/django-admin/auth/user/{IDS['membre']}/change/", hauteur=1900)
    ctx.close()
    nav.close()

# Conversion en JPEG optimisés (largeur 1500 px au maximum) pour le PDF.
for png in sorted(BRUT.glob("*.png")):
    if ONLY and not any(png.stem.startswith(n) for n in ONLY):
        continue
    image = Image.open(png).convert("RGB")
    if image.width > 1500:
        image = image.resize((1500, round(image.height * 1500 / image.width)), Image.LANCZOS)
    image.save(IMG / f"{png.stem}.jpg", quality=80, optimize=True)
print("Images mises à jour dans", IMG)
