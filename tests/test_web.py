"""Local search and rendering checks with an isolated SQLite fixture, not a MySQL integration test."""

import sqlite3
import json
import unittest
from unittest.mock import patch

from web.app import app


class PreviewDatabase:
    """Run the web query against a small SQL fixture without starting the cloud VM."""

    def __init__(self, rows):
        self.database = sqlite3.connect(":memory:", check_same_thread=False)
        self.database.row_factory = sqlite3.Row
        self.database.execute("CREATE TABLE cards (id TEXT, multiverseid INTEGER, name TEXT, card_text TEXT, "
                              "artist TEXT, set_code TEXT, image_url TEXT, source_json TEXT, details_json TEXT)")
        self.database.executemany("INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?)",
                                  [tuple(row) + (None,) * (9 - len(row)) for row in rows])

    def cursor(self):
        return PreviewCursor(self.database.cursor())

    def close(self):
        pass  # The fixture remains available across test-client requests.


class PreviewCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cursor.close()

    def execute(self, sql, parameters=()):
        self.cursor.execute(sql.replace("%s", "?"), parameters)

    def fetchone(self):
        row = self.cursor.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        return [dict(row) for row in self.cursor.fetchall()]


class WebTests(unittest.TestCase):
    def setUp(self):
        self.connection = PreviewDatabase([
            ("name-match", 1, "Manta Rider", "Ordinary text", "Alice", "TST", None),
            ("text-match", 2, "Another card", "This creature gains flying until end of turn.", "Bob", "TST", None),
            ("artist-match", 3, "Third card", "Pay 50%_ now", "Pete Venters", "TST", None),
            ("html-match", 4, "<script>alert(1)</script>", "Unsafe <b>text</b>", "Artist", "TST", None),
        ])
        self.patch = patch("web.app.connect_database", return_value=self.connection)
        self.patch.start()
        self.client = app.test_client()

    def test_detail_endpoint_preserves_all_source_fields_and_handles_missing_cards(self):
        original = {"id": "name-match", "name": "Manta Rider", "cmc": 0, "power": "*",
                    "future": {"enabled": False, "value": None}, "text": "<script>unsafe</script>"}
        self.connection.database.execute("UPDATE cards SET details_json=? WHERE id=?",
                                         (json.dumps(original), "name-match"))
        response = self.client.get("/cards/name-match")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["card"], original)
        self.assertEqual(self.client.get("/cards/missing").status_code, 404)
        self.assertEqual(self.client.get("/cards/'%20OR%201=1--").status_code, 404)
        self.assertEqual(self.client.get("/cards/" + "x" * 129).status_code, 400)

    def tearDown(self):
        self.patch.stop()
        self.connection.database.close()

    def test_one_search_matches_name_artist_and_middle_of_sentence(self):
        for query, identifier in (("mAnTa", "name-match"), ("gains flying until", "text-match"), ("Pete Venters", "artist-match")):
            result = self.client.get("/", query_string={"q": query})
            self.assertEqual(result.status_code, 200)
            self.assertIn(identifier.encode(), result.data)
            self.assertNotIn(b"<select", result.data)

    def test_literals_and_input_are_safe(self):
        self.assertIn(b"artist-match", self.client.get("/", query_string={"q": "50%_"}).data)
        for query in ("50%Z", "' OR 1=1 --", ".*", "not-present"):
            self.assertIn("Keine Karte gefunden".encode(), self.client.get("/", query_string={"q": query}).data)
        html = self.client.get("/", query_string={"q": "<script>"}).data
        self.assertIn(b"&lt;script&gt;", html)
        self.assertNotIn(b"<script>alert(1)</script>", html)
        invalid = self.client.get("/", query_string={"q": "x" * 201})
        self.assertEqual(invalid.status_code, 400)
        self.assertIn(b'role="alert"', invalid.data)
        self.assertIn("Bitte höchstens 200 Zeichen eingeben.".encode(), invalid.data)
        self.assertNotIn(b'class="landing-title"', invalid.data)

    def test_start_page_and_card_preview_markup(self):
        home = self.client.get("/").data
        self.assertIn(b'class="start-page"', home)
        self.assertNotIn(b'class="intro"', home)
        self.assertIn(b'class="dhbw-logo"', home)
        self.assertIn(b'class="magic-flame"', home)
        self.assertIn(b'<h1 class="landing-title">Karten finden</h1>', home)
        self.assertNotIn(b'class="landing-cards"', home)
        self.assertIn(b'class="search-examples"', home)
        self.assertIn(b'class="theme-toggle"', home)
        self.assertIn(b'src="/static/theme.js"', home)
        for path in ("/static/card-back.jpg", "/static/dhbw-logo.png", "/static/magic-symbol.png",
                     "/static/theme.js"):
            with self.client.get(path) as asset:
                self.assertEqual(asset.status_code, 200)
        result = self.client.get("/?q=manta").data
        self.assertIn(b'class="has-results"', result)
        self.assertIn(b'class="dhbw-logo"', result)
        self.assertIn(b'class="magic-flame"', result)
        self.assertIn(b'class="theme-toggle"', result)
        self.assertNotIn(b'class="landing-title"', result)
        self.assertNotIn(b'class="search-examples"', result)
        self.assertIn(b'img class="card-art" src="/static/card-back.jpg"', result)
        self.assertNotIn(b'artwork open-card image-unavailable', result)
        self.assertIn(b'aria-haspopup="dialog"', result)
        self.assertIn(b'<details class="card-data" data-card-id=', result)
        self.assertIn(b'<dialog id="card-dialog"', result)

    def test_results_stay_bounded(self):
        self.connection.database.executemany("INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?)",
                                            [(f"limit-{n}", None, "Limit", "", "", "", None, None, None) for n in range(60)])
        html = self.client.get("/?q=Limit").data
        self.assertEqual(html.count(b'<article class="card">'), 50)
        self.assertIn(b"Die ersten 50 Treffer", html)


if __name__ == "__main__":
    unittest.main()
