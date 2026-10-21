"""
Protection des contrats quand le site sert lui-même les médias
(SERVE_MEDIA=1, solution de secours si Apache ne sert pas /media/) : les
photos sont servies, jamais le dossier contrats_location/.

Lancement : python manage.py test calendrier.test_contrats_media
"""
import importlib
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import clear_url_caches

import concorde_site.urls


class ContratsNonServisTests(TestCase):
    def setUp(self):
        dossier = Path(self.enterContext(tempfile.TemporaryDirectory()))
        (dossier / "contrats_location").mkdir()
        (dossier / "contrats_location" / "contrat.pdf").write_bytes(b"%PDF confidentiel")
        (dossier / "photo.jpg").write_bytes(b"photo")
        self.enterContext(override_settings(DEBUG=False, SERVE_MEDIA=True, MEDIA_ROOT=dossier))
        # Les adresses sont construites à l'import : on les reconstruit avec
        # SERVE_MEDIA actif, puis on remet les adresses d'origine.
        importlib.reload(concorde_site.urls)
        self.addCleanup(clear_url_caches)
        self.addCleanup(importlib.reload, concorde_site.urls)
        clear_url_caches()

    def test_photo_servie_contrat_refuse(self):
        self.assertEqual(self.client.get("/media/photo.jpg").status_code, 200)
        reponse = self.client.get("/media/contrats_location/contrat.pdf")
        self.assertEqual(reponse.status_code, 404)
        self.assertNotIn(b"confidentiel", reponse.content)
