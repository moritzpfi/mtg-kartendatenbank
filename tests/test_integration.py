"""Opt-in checks against real HDFS, PySpark and the isolated mtg_test database."""

import hashlib
import json
import os
import unittest
from unittest.mock import patch
import uuid
from contextlib import contextmanager

from scripts.common import Hdfs, connect_database
from scripts.process_cards import database_summary, digest_rows, ensure_schema, process, publish_snapshot
from web.app import app
from scripts.text_cleaning import clean_card


def put_fixture(run_id, cards):
    """Explicit synthetic edge cases, stored in real HDFS; never production input."""
    hdfs = Hdfs()
    path = f"{hdfs.root}/raw/{run_id}"
    hdfs.mkdir(path)
    body = json.dumps({"cards": cards}, ensure_ascii=False).encode()
    hdfs.put(path + "/page_00001.json", body)
    manifest = {
        "run_id": run_id, "source": "synthetic integration-test fixture", "development": True,
        "download_complete": True, "hdfs_complete": True, "raw_count": len(cards),
        "total_counts": [len(cards)],
        "pages": [{"file": "page_00001.json", "count": len(cards), "sha256": hashlib.sha256(body).hexdigest()}],
    }
    hdfs.put(path + "/_manifest.json", json.dumps(manifest).encode())


@unittest.skipUnless(os.environ.get("RUN_INTEGRATION") == "1", "Requires the Compose services")
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.connection = connect_database(test=True)
        ensure_schema(self.connection)

    def tearDown(self):
        self.connection.close()

    def test_publication_rolls_back_and_repeats_safely(self):
        old = [("old", None, "Old snapshot", "", "", "OLD", None, '{"id":"old"}', '{"id":"old"}')]
        expected_old = {"final_count": 1, "sha256": digest_rows(old)}
        publish_snapshot(self.connection, old, expected_old)
        new = [("new", 42, "New snapshot", "flying", "Künstler", "NEW", None, '{"id":"new"}', '{"id":"new"}')]
        expected_new = {"final_count": 1, "sha256": digest_rows(new)}
        with self.assertRaisesRegex(RuntimeError, "Intentional"):
            publish_snapshot(self.connection, new, expected_new, fail_after_delete=True)
        self.assertEqual(database_summary(self.connection), {"count": 1, "sha256": expected_old["sha256"]})
        publish_snapshot(self.connection, new, expected_new)
        publish_snapshot(self.connection, new, expected_new)
        self.assertEqual(database_summary(self.connection), {"count": 1, "sha256": expected_new["sha256"]})

    def test_partial_batch_publication_rolls_back_every_insert(self):
        old = [("old", None, "Old snapshot", "", "", "OLD", None, '{"id":"old"}', '{"id":"old"}')]
        old_hash = digest_rows(old)
        publish_snapshot(self.connection, old, {"final_count": 1, "sha256": old_hash})
        rows = [(f"new-{n:04}", None, "New", "", "", "NEW", None, '{}', '{}') for n in range(2001)]
        original_cursor = self.connection.cursor
        inserts = 0

        @contextmanager
        def failing_cursor(*args, **kwargs):
            nonlocal inserts
            with original_cursor(*args, **kwargs) as cursor:
                execute = cursor.execute

                def interrupt_second_batch(sql, parameters=None):
                    nonlocal inserts
                    statement = sql.decode("utf-8") if isinstance(sql, (bytes, bytearray)) else sql
                    if statement.startswith("INSERT INTO cards ("):
                        inserts += 1
                        if inserts == 2:
                            raise RuntimeError("Intentional interruption after first inserted batch")
                    return execute(sql, parameters)

                with patch.object(cursor, "execute", side_effect=interrupt_second_batch):
                    yield cursor

        with patch.object(self.connection, "cursor", side_effect=failing_cursor):
            with self.assertRaisesRegex(RuntimeError, "after first inserted batch"):
                publish_snapshot(self.connection, rows, {"final_count": len(rows), "sha256": digest_rows(rows)})
        self.assertEqual(inserts, 2)
        self.assertEqual(database_summary(self.connection), {"count": 1, "sha256": old_hash})
        expected = {"final_count": len(rows), "sha256": digest_rows(rows)}
        publish_snapshot(self.connection, rows, expected)
        publish_snapshot(self.connection, rows, expected)
        self.assertEqual(database_summary(self.connection), {"count": len(rows), "sha256": expected["sha256"]})

    def test_search_fields_escaping_and_input_validation(self):
        source = {"id": "test-id", "name": "Manta <script>alert(1)</script>", "rarity": "Common",
                  "legalities": [{"format": "Modern", "legality": "Legal"}]}
        rows = [("test-id", None, "Manta <script>alert(1)</script>", "Flying 50%_", "Künstler Ö", "TST",
                 "https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=4711&type=card", json.dumps(source), json.dumps(source))]
        publish_snapshot(self.connection, rows, {"final_count": 1, "sha256": digest_rows(rows)})
        with patch.dict(os.environ, {"MTG_WEB_TEST_DATABASE": "1"}):
            client = app.test_client()
            for query in ("mAnTa", "FLYING", "künstler ö", "50%_"):
                result = client.get("/", query_string={"q": query})
                self.assertEqual(result.status_code, 200)
                self.assertIn(b"test-id", result.data)
                self.assertNotIn(b"<script>alert(1)</script>", result.data)
                self.assertIn(b'loading="lazy"', result.data)
                self.assertIn(b'img class="card-art"', result.data)
            self.assertIn("Keine Karte gefunden".encode(), client.get("/?q=nonexistent").data)
            self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(client.get("/", query_string={"q": "x" * 201}).status_code, 400)
            self.assertIn("Keine Karte gefunden".encode(), client.get("/", query_string={"q": "' OR 1=1 --"}).data)
            self.assertEqual(client.get("/cards/test-id").get_json()["card"], source)

    def test_transform_real_hdfs_and_mysql_with_edge_cases(self):
        run_id = "test_" + uuid.uuid4().hex
        card = {"id": "fixture-a", "name": " Manta ", "text": "Flying", "artist": None, "set": "TST"}
        other = {"id": "fixture-b", "name": "Other", "multiverseid": "123", "artist": "Künstler",
                 "futureField": {"number": 0, "values": ["Ä", False, None]}, "legalities": [{"format": "Modern", "legality": "Legal"}],
                 "foreignNames": [{"name": "A\u0090", "text": "Vol\n\u0081À chaque fois &amp; Boo"}],
                 "rulings": [{"text": " <sad trombone noises> "}], "originalText": "{1}\u200b less"}
        put_fixture(run_id, [card, card, other, {"name": "Missing ID"}, {"id": "missing-name"}])
        summary = process("transform", run_id)
        self.assertEqual((summary["raw_count"], summary["invalid_count"], summary["duplicate_count"], summary["final_count"]), (5, 2, 1, 2))
        self.assertEqual(summary["data_quality"]["verified_sha256_pages"], 1)
        self.assertEqual(summary["data_quality"]["changes"]["missing_artist_to_empty"], 2)
        self.assertEqual(summary["text_cleaning"]["changed_cards"], 1)
        files = Hdfs().list(summary["hdfs_final_path"])
        self.assertTrue(all(entry["replication"] == 1 for entry in files if entry["pathSuffix"].endswith(".parquet")))
        process("validate-final", run_id)
        with self.assertRaisesRegex(ValueError, "test database"):
            process("load", run_id)
        process("load", run_id, test_database=True)
        process("validate-database", run_id, test_database=True)
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT source_json,details_json FROM cards WHERE id=%s", ("fixture-b",))
            source, details = cursor.fetchone()
            self.assertEqual(json.loads(source), other)
            self.assertEqual(json.loads(details), clean_card(other)[0])
        with patch.dict(os.environ, {"MTG_WEB_TEST_DATABASE": "1"}):
            self.assertEqual(app.test_client().get("/cards/fixture-b").get_json()["card"], clean_card(other)[0])
        process("load", run_id, test_database=True)

    def test_conflicting_ids_prevent_publication(self):
        run_id = "conflict_" + uuid.uuid4().hex
        put_fixture(run_id, [{"id": "same", "name": "One"}, {"id": "same", "name": "Two"}])
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            process("transform", run_id)


if __name__ == "__main__":
    unittest.main()
