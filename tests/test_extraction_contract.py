import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

import extract_entities
from entity_extraction.entities import item_key

TEXT = " <!--td {x}-->Ada\xa0graduated in 1956. "
KEY = "d1923c2ad7533d8e4dd515fa834177bb1143b7f849da614132a984a2dcefd53e"


class FakeExtractor:
    def __init__(self, model, threshold):
        pass

    def extract(self, field, subject, text):
        return [{"type": "place", "value": "Marburg", "context": text}]


class ExtractionContractTests(unittest.TestCase):
    def test_key_matches_integration_contract(self):
        self.assertEqual(KEY, item_key("BIOGRAPHY", TEXT))

    def test_workbook_produces_compatible_json_and_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workbook_path = root / "Person.xlsx"
            output_path = root / "Person_entities.json"
            workbook = Workbook()
            workbook.active.append(["Unique_ID", "Name_Surname", "Biography"])
            workbook.active.append(["P_1", "Ada", TEXT])
            workbook.save(workbook_path)

            with patch("entity_extraction.gliner_extractor.GlinerExtractor", FakeExtractor):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(0, extract_entities.main([
                        "--file", str(workbook_path), "--fields", "Biography",
                        "--output", str(output_path),
                    ]))

            store = json.loads(output_path.read_text(encoding="utf-8"))
            item = store["items"][KEY]
            self.assertEqual((1, "BIOGRAPHY", "Ada", "P_1"),
                             (store["version"], item["field"], item["subject"], item["subject_id"]))
            self.assertEqual("Marburg", item["entities"][0]["value"])
            event = next(entity for entity in item["entities"] if entity["type"] == "event")
            self.assertEqual(("Graduation", "Ada graduated in 1956."),
                             (event["value"], event["context"]))

            timeline = ET.parse(root / "Person_entities_timeline.xml")
            self.assertEqual("P_1", timeline.findtext("person/unique_id"))
            entry = timeline.find("person/timeline/entry")
            self.assertEqual("event", entry.get("category"))
            self.assertEqual("Graduation", entry.findtext("type"))
            self.assertEqual("1956-01-01", entry.findtext("begin"))

    @unittest.skipUnless(os.environ.get("TRANSFORMER_REPO"), "set TRANSFORMER_REPO to test integration")
    def test_outputs_are_consumed_by_transformer(self):
        transformer = Path(os.environ["TRANSFORMER_REPO"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workbook_path = root / "Person.xlsx"
            json_path = root / "Person_entities.json"
            workbook = Workbook()
            workbook.active.append(["Unique_ID", "Name_Surname", "Biography"])
            workbook.active.append(["P_1", "Ada", TEXT])
            workbook.save(workbook_path)
            with patch("entity_extraction.gliner_extractor.GlinerExtractor", FakeExtractor):
                with contextlib.redirect_stdout(io.StringIO()):
                    extract_entities.main([
                        "--file", str(workbook_path), "--fields", "Biography", "--output", str(json_path),
                    ])

            subprocess.run([
                sys.executable, str(transformer / "script/download_drive_excel.py"),
                "--file", str(workbook_path), "--entities", str(json_path),
                "--output-dir", str(root / "output"), "--base-name", "person",
            ], check=True, capture_output=True, text=True)
            entities = ET.parse(root / "output/person/Sheet_entities.xml")
            self.assertEqual("Graduation", entities.findtext("row/Events/Event/Label"))
            self.assertEqual("P_1", entities.findtext("row/Unique_ID"))

            rdf_path = root / "timeline.ttl"
            subprocess.run([
                sys.executable, str(transformer / "script/xml_to_rdf.py"),
                "--mapping", str(transformer / "script/mappings/e21_timeline.yaml"),
                "--xml", str(root / "Person_entities_timeline.xml"), "--out", str(rdf_path),
            ], check=True, capture_output=True, text=True)
            self.assertIn("person/P_1", rdf_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
