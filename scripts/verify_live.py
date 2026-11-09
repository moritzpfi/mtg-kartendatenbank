"""Record real database, HDFS and HTTP-search evidence for a completed snapshot."""

import argparse
from datetime import datetime, timezone
import json
from urllib.parse import quote

import requests

from scripts.common import Hdfs, connect_database, run_directory, save_json
from scripts.process_cards import database_field_counts, database_summary
from scripts.audit_text import audit


def verify(run_id, web_url):
    directory = run_directory(run_id)
    hdfs = Hdfs()
    raw = json.loads(hdfs.read(f"{hdfs.root}/raw/{run_id}/_manifest.json"))
    final = json.loads(hdfs.read(f"{hdfs.root}/final/{run_id}/_summary.json"))
    if raw["development"] or not raw["hdfs_complete"]:
        raise ValueError("This verification requires a complete regular HDFS snapshot")
    connection = connect_database()
    try:
        actual = database_summary(connection)
        if actual != {"count": final["final_count"], "sha256": final["sha256"]}:
            raise ValueError("Database differs from final snapshot")
        field_counts = database_field_counts(connection)
        if field_counts != final["final_field_counts"]:
            raise ValueError("Database field counts differ from audited final snapshot")
        text_audit = audit(run_id)
        source_details = {"raw_pages_checked": text_audit["verified_sha256_utf8_pages"],
                          "source_records_checked": text_audit["database"]["count"],
                          **text_audit["database"]}
        if source_details["mismatches"] or source_details["missing_expected_ids"]:
            raise ValueError("Original or cleaned database details differ from the expected raw transformation")
        searches = []
        for field, column, term in (("name", "name", "Manta"), ("text", "card_text", "flying"),
                                    ("artist", "artist", "Pete Venters")):
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT id FROM cards WHERE LOWER({column}) LIKE LOWER(%s) ORDER BY name,id LIMIT 1",
                               ("%" + term + "%",))
                expected = cursor.fetchone()
            if not expected:
                raise ValueError("No real source card for the documented search: " + term)
            response = requests.get(web_url, params={"q": term}, timeout=30)
            response.raise_for_status()
            if expected[0] not in response.text:
                raise AssertionError("Search response is missing the expected real card")
            searches.append({"field": field, "term": term, "status": response.status_code,
                             "expected_card_id_found": expected[0]})
        empty = requests.get(web_url, params={"q": "__mtg_no_match_9e3ba0b9__"}, timeout=30)
        if empty.status_code != 200 or "Keine Karte gefunden" not in empty.text:
            raise AssertionError("No-match search did not return the expected message")
        detail_response = requests.get(web_url.rstrip("/") + "/cards/" + quote(searches[0]["expected_card_id_found"], safe=""), timeout=30)
        detail_response.raise_for_status()
        if detail_response.json()["card"]["id"].strip() != searches[0]["expected_card_id_found"]:
            raise AssertionError("Detail endpoint did not return the requested source card")
        cleaned_examples = []
        for examples in text_audit["text_cleaning"]["examples"].values():
            identifier = examples[0]["id"]
            with connection.cursor() as cursor:
                cursor.execute("SELECT details_json FROM cards WHERE id=%s", (identifier,))
                expected = json.loads(cursor.fetchone()[0])
            response = requests.get(web_url.rstrip("/") + "/cards/" + quote(identifier, safe=""), timeout=30)
            response.raise_for_status()
            if response.json()["card"] != expected:
                raise AssertionError("HTTP details differ from the cleaned database object")
            cleaned_examples.append({"id": identifier, "status": response.status_code, "cleaned_object_matches": True})
    finally:
        connection.close()
    result = {"verified_at": datetime.now(timezone.utc).isoformat(), "run_id": run_id,
              "raw": raw, "final": final, "database": actual, "database_field_counts": field_counts, "searches": searches,
              "no_match_status": empty.status_code, "source_details": source_details,
              "detail_endpoint_status": detail_response.status_code}
    result["cleaned_http_examples"] = cleaned_examples
    result["text_cleaning"] = text_audit["text_cleaning"]
    save_json(directory / "live_verification.json", result)
    print(json.dumps({"run_id": run_id, "raw_count": raw["raw_count"],
                      "final_count": final["final_count"], "database": actual,
                      "searches": searches, "source_details": source_details}, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--web-url", default="http://web:5000/")
    options = parser.parse_args()
    verify(options.run_id, options.web_url)
