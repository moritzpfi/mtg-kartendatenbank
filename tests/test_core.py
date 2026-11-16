import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

import requests

from scripts import fetch_cards
from scripts.cards import (COLUMNS, FIELDS, audit_raw, canonical_cards, inspect_card,
                           normalize_image_url, reduced_card, write_quality_report)
from scripts.common import Hdfs, run_directory
from collections import Counter
from web.app import escaped_like
from scripts.process_cards import ensure_schema, final_data


def response(cards, total, next_page=None, status=200):
    result = requests.Response()
    result.status_code = status
    result.url = "https://example.invalid/cards"
    result._content = json.dumps({"cards": cards}).encode()
    result.headers["Total-Count"] = str(total)
    result.headers["Ratelimit-Limit"] = "1000"
    result.headers["Ratelimit-Remaining"] = "999"
    if next_page:
        result.headers["Link"] = f'<https://example.invalid/cards?page={next_page}&pageSize=100>; rel="next"'
    return result


class CoreTests(unittest.TestCase):
    def test_final_payload_only_retains_required_fields_without_changing_raw(self):
        card = {"id": "a", "name": "Künstler", "power": "*", "cmc": 0,
                "subtypes": ["Merfolk", "Wizard"], "text": "{U}: Flying\nNext line", "flavor": "A <story> & more",
                "futureField": {"enabled": False, "missing": None, "items": ["Ä", 3]},
                "originalText": "Flying\u200b", "rulings": [{"text": " A ruling "}],
                "foreignNames": [{"name": "\u0081Name", "text": "A &amp; B"}],
                "legalities": [{"format": "Modern", "legality": "Legal"}]}
        page = json.dumps({"cards": [card]}, ensure_ascii=False).encode("utf-8")
        payloads = canonical_cards(page)
        self.assertEqual(json.loads(payloads[0]), {
            "id": "a", "name": "Künstler", "subtypes": '["Merfolk","Wizard"]',
            "card_text": "{U}: Flying\nNext line", "flavor": "A <story> & more", "artist": "", "image_url": None,
        })
        self.assertEqual(json.loads(page)["cards"][0], card)
        self.assertEqual(set(json.loads(payloads[0])), set(COLUMNS))
        reordered = dict(reversed(list(card.items())))
        self.assertEqual(canonical_cards(json.dumps({"cards": [reordered]}).encode())[0], payloads[0])

    def test_projection_normalizes_missing_values_and_rejects_bad_retained_types(self):
        self.assertEqual(reduced_card({"id": " a ", "name": " A "}), {
            "id": "a", "name": "A", "subtypes": "[]", "card_text": "", "flavor": "", "artist": "", "image_url": None,
        })
        for fields in ({"subtypes": "Merfolk"}, {"subtypes": ["Merfolk", 5]}, {"flavor": 5}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                reduced_card({"id": "a", "name": "A", **fields})

    def test_legacy_and_extra_final_columns_require_reprocessing(self):
        hdfs, spark = Mock(), Mock()
        hdfs.root = "/mtg"
        with patch("scripts.process_cards.Hdfs", return_value=hdfs):
            hdfs.read.return_value = json.dumps({"export_columns": list(COLUMNS)}).encode()
            with self.assertRaisesRegex(ValueError, "run transform again"):
                final_data(spark, "old")
            spark.read.parquet.assert_not_called()
            hdfs.read.return_value = json.dumps({"schema_version": 2, "export_columns": list(COLUMNS)}).encode()
            spark.read.parquet.return_value.columns = list(COLUMNS) + ["source_json"]
            with self.assertRaisesRegex(ValueError, "exactly the seven"):
                final_data(spark, "extra")

    def test_database_schema_check_never_drops_legacy_columns(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [(name,) for name in ("id", "name", "source_json")]
        with self.assertRaisesRegex(ValueError, "backed-up migration"):
            ensure_schema(connection)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertFalse(any(statement.startswith(("ALTER", "DROP", "DELETE")) for statement in statements))

    def test_quality_report_calculates_percentages_for_each_run(self):
        evidence = Path(__file__).resolve().parent / "fixtures"
        summary = json.loads((evidence / "final_summary.json").read_text(encoding="utf-8"))
        database = json.loads((evidence / "database_summary.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"WORK_DIR": directory}):
            write_quality_report(summary, database)
            report = (Path(directory) / summary["run_id"] / "quality_report.md").read_text(encoding="utf-8")
            self.assertIn("| Finaldatensätze | 93643 | 100,000 % |", report)
            self.assertIn("| Fehlender Künstler zu leerem Suchtext | 9 | 0,010 % |", report)
            summary["raw_count"] = 100
            summary["data_quality"]["changes"]["missing_artist_to_empty"] = 7
            write_quality_report(summary, database)
            report = (Path(directory) / summary["run_id"] / "quality_report.md").read_text(encoding="utf-8")
            self.assertIn("| Fehlender Künstler zu leerem Suchtext | 7 | 7,000 % |", report)

    def test_image_urls_require_the_known_https_source(self):
        self.assertEqual(normalize_image_url("http://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=4711&type=card"),
                         "https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=4711&type=card")
        for unsafe in (None, "", "javascript:alert(1)", "http://127.0.0.1/admin", "https://user:password@gatherer.wizards.com/card"):
            self.assertIsNone(normalize_image_url(unsafe))

    def test_quality_counts_missing_values_and_subtype_arrays(self):
        fields = {name: Counter() for name in FIELDS}
        changes = Counter()
        inspect_card({"id": " a ", "name": " A ", "subtypes": ["Merfolk"]}, fields, changes,
                     Counter(), Counter(), Counter(), {"image_examples": []})
        self.assertEqual(changes["id_trimmed"], 1)
        self.assertEqual(changes["missing_text_to_empty"], 1)
        self.assertEqual(changes["missing_flavor_to_empty"], 1)
        self.assertEqual(fields["subtypes"]["arrays"], 1)
        self.assertEqual(fields["subtypes"]["non_string"], 0)
        self.assertEqual(changes["rows_with_value_cleaning"], 1)

    def test_raw_audit_rejects_modified_hdfs_bytes(self):
        hdfs = Mock()
        hdfs.read.return_value = b'{"cards":[]}'
        manifest = {"run_id": "corrupt", "download_complete": True, "hdfs_complete": True,
                    "raw_count": 0, "pages": [{"file": "page.json", "sha256": "wrong", "count": 0}]}
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            audit_raw(hdfs, manifest)

    def test_quality_flags_replacement_and_control_characters(self):
        fields = {name: Counter() for name in FIELDS}
        inspect_card({"id": "a", "name": "A\ufffd", "text": "bad\x01text"}, fields, Counter(),
                     Counter(), Counter(), Counter(), {"image_examples": []})
        self.assertEqual(fields["name"]["replacement_character"], 1)
        self.assertEqual(fields["text"]["unexpected_control_characters"], 1)

    def test_run_id_cannot_escape_its_directory(self):
        for identifier in ("../other", "/tmp/other", "a/b", "", "a" * 101):
            with self.assertRaises(ValueError):
                run_directory(identifier)

    def test_literal_search_wildcards(self):
        self.assertEqual(escaped_like("50%_!"), "%50!%!_!!%")

    def test_transient_http_failure_is_retried(self):
        session = Mock()
        session.get.side_effect = [response([], 1, status=503), response([{"id": "one"}], 1)]
        sleeps = []
        body, cards, _ = fetch_cards.get_page(session, "https://example.invalid/cards", 1, 0, sleeps.append)
        self.assertEqual(cards, [{"id": "one"}])
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(json.loads(body)["cards"], cards)
        self.assertGreater(sleeps[0], 0)

    def test_pagination_and_original_bytes(self):
        first = response([{"id": str(n)} for n in range(100)], 101, next_page=2)
        second = response([{"id": "last"}], 101)
        session = Mock()
        session.headers = {}
        session.get.side_effect = [first, second]
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "WORK_DIR": directory, "MTG_API_URL": "https://example.invalid/cards", "MTG_REQUEST_INTERVAL": "0",
        }), patch.object(fetch_cards.requests, "Session", return_value=session):
            manifest = fetch_cards.fetch("complete", download_only=True)
            self.assertTrue(manifest["download_complete"])
            self.assertFalse(manifest["hdfs_complete"])
            self.assertEqual(manifest["raw_count"], 101)
            actual = (Path(directory) / "complete/raw/page_00001.json").read_bytes()
            self.assertEqual(actual, first.content)
            self.assertEqual(manifest["pages"][0]["sha256"], hashlib.sha256(actual).hexdigest())
            # A retry reuses the completed immutable download.
            fetch_cards.fetch("complete", download_only=True)
            self.assertEqual(session.get.call_count, 2)

    def test_truncated_snapshot_is_rejected(self):
        session = Mock()
        session.headers = {}
        session.get.return_value = response([{"id": "one"}], 101)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "WORK_DIR": directory, "MTG_API_URL": "https://example.invalid/cards", "MTG_REQUEST_INTERVAL": "0",
        }), patch.object(fetch_cards.requests, "Session", return_value=session):
            with self.assertRaisesRegex(RuntimeError, "Incomplete"):
                fetch_cards.fetch("incomplete", download_only=True)
            manifest = json.loads((Path(directory) / "incomplete/raw_manifest.json").read_text())
            self.assertFalse(manifest["download_complete"])
            self.assertFalse(manifest["hdfs_complete"])

    def test_resume_preserves_already_downloaded_pages(self):
        first = response([{"id": str(n)} for n in range(100)], 101, next_page=2)
        last = response([{"id": "last"}], 101)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "WORK_DIR": directory, "MTG_API_URL": "https://example.invalid/cards", "MTG_REQUEST_INTERVAL": "0",
        }), patch.object(fetch_cards, "get_page") as getter:
            getter.side_effect = [(first.content, first.json()["cards"], first), RuntimeError("connection lost")]
            with self.assertRaisesRegex(RuntimeError, "connection lost"):
                fetch_cards.fetch("resume", download_only=True)
            getter.reset_mock()
            getter.side_effect = None
            getter.return_value = (last.content, last.json()["cards"], last)
            manifest = fetch_cards.fetch("resume", download_only=True)
            self.assertTrue(manifest["download_complete"])
            self.assertEqual(manifest["raw_count"], 101)
            self.assertEqual(getter.call_count, 1)
            self.assertEqual(getter.call_args.args[2], 2)

    def test_changed_source_total_is_rejected(self):
        session = Mock()
        session.headers = {}
        session.get.side_effect = [response([{}] * 100, 101, 2), response([{}], 102)]
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "WORK_DIR": directory, "MTG_API_URL": "https://example.invalid/cards", "MTG_REQUEST_INTERVAL": "0",
        }), patch.object(fetch_cards.requests, "Session", return_value=session):
            with self.assertRaisesRegex(RuntimeError, "changed"):
                fetch_cards.fetch("changing", download_only=True)

    def test_hdfs_uses_the_datanode_redirect(self):
        hdfs = Hdfs()
        redirect = Mock(status_code=307, headers={"Location": "http://data.invalid/file"})
        hdfs.request = Mock(return_value=redirect)
        hdfs.session = Mock()
        hdfs.session.put.return_value = Mock(status_code=201)
        hdfs.put("/test/file", b"original bytes")
        self.assertEqual(hdfs.session.put.call_args.kwargs["data"], b"original bytes")
        self.assertEqual(hdfs.session.put.call_args.args[0], "http://data.invalid/file")


if __name__ == "__main__":
    unittest.main()
