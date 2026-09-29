import unittest
from unittest.mock import patch

from provider_fetcher import server


class WarmCatalogTests(unittest.TestCase):
    def test_warm_catalog_refreshes_even_when_cache_exists(self):
        with patch.object(server.Catalog, "refresh") as refresh:
            server._warm_catalog()
        refresh.assert_called_once_with()

    def test_warm_catalog_survives_offline(self):
        with patch.object(server.Catalog, "refresh", side_effect=OSError("offline")):
            server._warm_catalog()


if __name__ == "__main__":
    unittest.main()
