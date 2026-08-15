from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from analysis.price_history import new_listings, price_changes
from collectors.carmax import fetch_from_apify, load_export, load_search_config
from database import connect, save_snapshot
from reports.notebooklm import build_markdown


class MvpFlowTests(unittest.TestCase):
    def test_two_scans_detect_new_listing_and_price_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_export = root / "first.json"
            second_export = root / "second.json"
            first_export.write_text(
                json.dumps([{"vin": "VIN00000000000001", "year": 2021, "make": "Toyota", "model": "RAV4", "price": 25000, "mileage": 40000}]),
                encoding="utf-8",
            )
            second_export.write_text(
                json.dumps([
                    {"vin": "VIN00000000000001", "year": 2021, "make": "Toyota", "model": "RAV4", "price": 24000, "mileage": 40000},
                    {"vin": "VIN00000000000002", "year": 2020, "make": "Honda", "model": "CR-V", "price": 23000, "mileage": 45000},
                ]),
                encoding="utf-8",
            )
            with closing(connect(root / "test.db")) as connection:
                save_snapshot(connection, load_export(first_export), source_file=str(first_export))
                second_scan = save_snapshot(connection, load_export(second_export), source_file=str(second_export))
                self.assertEqual(1, len(new_listings(connection, second_scan)))
                changes = price_changes(connection, second_scan)
                self.assertEqual(-1000, changes[0]["change_amount"])
                self.assertIn("Price changes: 1", build_markdown(connection, second_scan))

    def test_live_collector_uses_bearer_header_and_normalizes_items(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self) -> bytes:
                return json.dumps([
                    {
                        "vin": "VIN00000000000003",
                        "year": 2022,
                        "make": "Honda",
                        "model": "CR-V",
                        "price": 26998,
                        "detailUrl": "https://www.carmax.com/car/123",
                    }
                ]).encode("utf-8")

        search = {"name": "test", "actor_input": {"zips": ["20001"]}}
        with patch("collectors.carmax.urlopen", return_value=FakeResponse()) as mocked:
            listings = fetch_from_apify(
                search,
                token="secret-test-token",
                actor_id="e-commerce/carmax-zipcode-search-scraper",
                timeout_seconds=60,
                max_items=10,
            )
        request = mocked.call_args.args[0]
        self.assertEqual("Bearer secret-test-token", request.get_header("Authorization"))
        self.assertNotIn("secret-test-token", request.full_url)
        self.assertIn("e-commerce~carmax-zipcode-search-scraper", request.full_url)
        self.assertEqual("https://www.carmax.com/car/123", listings[0]["url"])

    def test_search_config_refuses_zip_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "searches.json"
            config.write_text(
                json.dumps({"searches": [{"name": "local", "actor_input": {"zips": ["YOUR_ZIP_CODE"]}}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Replace YOUR_ZIP_CODE"):
                load_search_config(config)


if __name__ == "__main__":
    unittest.main()
