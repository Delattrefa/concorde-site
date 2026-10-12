"""
Convertit manuel.html en PDF (A4, numéros de page en pied) avec Chrome.

Usage : python rendu.py [chemin_du_pdf]
Par défaut : docs/Manuel d'utilisation - Site La Concorde.pdf
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

MANUEL = Path(__file__).resolve().parent.parent
SORTIE = Path(sys.argv[1]) if len(sys.argv) > 1 else MANUEL.parent / "Manuel d'utilisation - Site La Concorde.pdf"

PIED = (
    '<div style="width:100%;font-size:7.5pt;color:#8a7d7d;padding:0 17mm;display:flex;'
    'justify-content:space-between;font-family:Arial">'
    "<span>La Concorde asbl — Manuel d'utilisation du site</span>"
    '<span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>'
)

with sync_playwright() as p:
    nav = p.chromium.launch(channel="chrome")
    page = nav.new_page()
    page.goto((MANUEL / "manuel.html").as_uri(), wait_until="networkidle")
    page.pdf(
        path=str(SORTIE), format="A4", print_background=True, prefer_css_page_size=True,
        display_header_footer=True, header_template="<span></span>", footer_template=PIED,
        outline=True, tagged=True,
    )
    nav.close()
print("PDF généré :", SORTIE)
