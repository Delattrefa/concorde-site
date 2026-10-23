"""
Convertit un manuel HTML en PDF (A4, numéros de page en pied) avec Chrome.

Usage : python rendu.py [membres] [chemin_du_pdf]
  sans argument : manuel.html → docs/Manuel d'utilisation - Site La Concorde.pdf
  membres       : manuel-membres.html → docs/Manuel des membres - Site La Concorde.pdf
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

MANUEL = Path(__file__).resolve().parent.parent
MANUELS = {
    "complet": ("manuel.html", "Manuel d'utilisation - Site La Concorde.pdf", "Manuel d'utilisation du site"),
    "membres": ("manuel-membres.html", "Manuel des membres - Site La Concorde.pdf", "Manuel des membres"),
}

arguments = sys.argv[1:]
choix = arguments.pop(0) if arguments and arguments[0] in MANUELS else "complet"
source, nom_pdf, intitule = MANUELS[choix]
SORTIE = Path(arguments[0]) if arguments else MANUEL.parent / nom_pdf

PIED = (
    '<div style="width:100%;font-size:7.5pt;color:#8a7d7d;padding:0 17mm;display:flex;'
    'justify-content:space-between;font-family:Arial">'
    f"<span>La Concorde asbl — {intitule}</span>"
    '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
)

with sync_playwright() as p:
    nav = p.chromium.launch(channel="chrome")
    page = nav.new_page()
    page.goto((MANUEL / source).as_uri(), wait_until="networkidle")
    page.pdf(
        path=str(SORTIE), format="A4", print_background=True, prefer_css_page_size=True,
        display_header_footer=True, header_template="<span></span>", footer_template=PIED,
        outline=True, tagged=True,
    )
    nav.close()
print("PDF généré :", SORTIE)
