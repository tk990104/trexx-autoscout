from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from analysis.price_history import new_listings, price_changes
from collectors.carmax import load_export
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


if __name__ == "__main__":
    unittest.main()
