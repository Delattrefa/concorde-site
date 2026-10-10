"""
Lanceur de tests du projet (TEST_RUNNER dans settings/base.py).

Pendant les tests, rien n'est écrit là où le site de développement lit :
- les fichiers envoyés vont dans un dossier temporaire, supprimé à la fin,
  et jamais dans src/media/ (la migration calendrier.0004 y copie
  notamment les annexes du contrat-type à chaque création de la base de
  test) ;
- le cache est en mémoire, propre aux tests, et non le cache sur disque
  src/tmp/cache/ partagé avec le site : sinon les sites Wagtail fictifs
  des tests (testserver) restaient en cache et cassaient les liens des
  pages du site de développement.
Les fichiers statiques sont servis sans le manifeste de collectstatic,
inutile ici.
"""
import shutil
import tempfile

from django.test import override_settings
from django.test.runner import DiscoverRunner


class ConcordeTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media_tests = tempfile.mkdtemp(prefix="concorde-tests-media-")
        self._reglages_tests = override_settings(
            MEDIA_ROOT=self._media_tests,
            CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
            STORAGES={
                "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            },
        )
        self._reglages_tests.enable()

    def teardown_test_environment(self, **kwargs):
        self._reglages_tests.disable()
        shutil.rmtree(self._media_tests, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
