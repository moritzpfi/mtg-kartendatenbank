"""Download original API responses and publish the raw snapshot to HDFS."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
import os
import time
from urllib.parse import parse_qs, urlparse

import requests

from scripts.common import Hdfs, run_directory, save_json

LOG = logging.getLogger(__name__)


def get_page(session, url, page, interval, sleeper=time.sleep):
    """Retry temporary failures, but never silently skip a page."""
    for attempt in range(5):
        try:
            response = session.get(url, params={"page": page, "pageSize": 100}, timeout=(15, 90))
            response.raise_for_status()
            body = response.content
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("cards"), list):
                raise ValueError("API response is not an object with a cards array")
            if len(payload["cards"]) > 100 or any(not isinstance(c, dict) for c in payload["cards"]):
                raise ValueError("Invalid cards array")
            sleeper(interval)
            return body, payload["cards"], response
        except requests.RequestException as error:
            response = error.response
            status = response.status_code if response is not None else None
            if status is not None and status not in (403, 429, 500, 502, 503, 504):
                raise
            if status == 403 and "rate limit" not in response.text.lower():
                raise
            if attempt == 4:
                raise
            delay = max(interval, min(60 * (2 ** attempt), 900))
            if response is not None:
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = max(delay, int(retry_after))
            LOG.warning("Page %s failed (%s); retry in %ss", page, error, delay)
            sleeper(delay)


def fetch(run_id, max_pages=0, download_only=False):
    if max_pages < 0:
        raise ValueError("max-pages must be zero (full) or positive (development)")
    directory = run_directory(run_id)
    manifest_path = directory / "raw_manifest.json"
    manifest = None
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["max_pages"] != max_pages:
            raise ValueError("Use a new run-id when changing development/full mode")
        # A completed download may be uploaded/retried without consuming the API again.
        if manifest.get("download_complete"):
            LOG.info("Reusing completed raw download for %s; no new API requests", run_id)
            return upload(run_id, manifest) if not download_only else manifest
        if manifest.get("invalid_source"):
            raise ValueError("Source changed; use a new run-id for a fresh snapshot")
        for saved in manifest["pages"]:
            content = (directory / "raw" / saved["file"]).read_bytes()
            if hashlib.sha256(content).hexdigest() != saved["sha256"]:
                raise ValueError("Previously downloaded raw page changed")
    raw = directory / "raw"
    raw.mkdir(exist_ok=True)
    url = os.environ.get("MTG_API_URL", "https://api.magicthegathering.io/v1/cards")
    interval = float(os.environ.get("MTG_REQUEST_INTERVAL", "1"))
    if interval < 0:
        raise ValueError("request interval cannot be negative")
    if manifest and manifest["source"] != url:
        raise ValueError("Source URL changed; use a new run-id")
    manifest = manifest or {
        "run_id": run_id, "source": url, "started_at": datetime.now(timezone.utc).isoformat(),
        "max_pages": max_pages, "development": max_pages > 0, "pages": [],
        "total_counts": [], "raw_count": 0, "download_complete": False, "hdfs_complete": False,
    }
    save_json(manifest_path, manifest)
    session = requests.Session()
    session.headers["User-Agent"] = "MTG-API-Practical-Exam/1.0"
    page = len(manifest["pages"]) + 1
    try:
        while True:
            if max_pages and len(manifest["pages"]) >= max_pages:
                break
            if manifest["pages"] and manifest.get("next_page", page) is None:
                break
            body, cards, response = get_page(session, url, page, interval)
            total = response.headers.get("Total-Count")
            if total is not None:
                total = int(total)
                if total < 1:
                    raise ValueError("Empty source snapshot is not publishable")
                if total not in manifest["total_counts"]:
                    manifest["total_counts"].append(total)
                if len(manifest["total_counts"]) > 1:
                    manifest["invalid_source"] = True
                    save_json(manifest_path, manifest)
                    raise RuntimeError("Source Total-Count changed during download; retry a new snapshot")
            remaining = response.headers.get("Ratelimit-Remaining")
            limit = response.headers.get("Ratelimit-Limit")
            manifest["rate_limit"] = limit
            # The header is an hourly quota, not a required delay between requests.
            # A full snapshot must fit the remaining budget before we start it.
            if total is not None and not max_pages and remaining and remaining.isdigit():
                if math.ceil(total / 100) - page > int(remaining):
                    raise RuntimeError("Not enough API quota for a complete snapshot; retry after reset")
            name = f"page_{page:05d}.json"
            temporary = raw / (name + ".tmp")
            temporary.write_bytes(body)
            temporary.replace(raw / name)
            manifest["pages"].append({
                "file": name, "count": len(cards), "sha256": hashlib.sha256(body).hexdigest(),
            })
            manifest["raw_count"] += len(cards)
            LOG.info("Page %s: %s cards; total %s", page, len(cards), manifest["raw_count"])
            next_url = response.links.get("next", {}).get("url")
            next_page = None
            if next_url:
                parsed = urlparse(next_url)
                if parsed.netloc != urlparse(url).netloc or parsed.path != urlparse(url).path:
                    raise ValueError("Unexpected pagination target")
                next_page = int(parse_qs(parsed.query)["page"][0])
                if next_page != page + 1:
                    raise ValueError("Pagination skipped or repeated a page")
            manifest["next_page"] = next_page
            save_json(manifest_path, manifest)
            if not next_page or (max_pages and page >= max_pages):
                break
            if remaining and remaining.isdigit() and int(remaining) <= 1:
                raise RuntimeError("API quota exhausted before completion; retry after reset")
            page = next_page
        if not manifest["raw_count"]:
            raise ValueError("No cards downloaded")
        if not max_pages and manifest["total_counts"]:
            expected = manifest["total_counts"][0]
            if manifest["raw_count"] != expected:
                raise RuntimeError(f"Incomplete source: {manifest['raw_count']} of {expected} cards")
            if len(manifest["pages"]) != math.ceil(expected / 100):
                raise RuntimeError("Page count does not match Total-Count")
        if not max_pages and not manifest["total_counts"]:
            manifest["completeness_note"] = "No Total-Count; followed all next links to the end"
        manifest["download_complete"] = True
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_json(manifest_path, manifest)
    finally:
        session.close()
    return manifest if download_only else upload(run_id, manifest)


def upload(run_id, manifest):
    directory = run_directory(run_id)
    hdfs = Hdfs()
    path = f"{hdfs.root}/raw/{run_id}"
    hdfs.mkdir(path)
    for page in manifest["pages"]:
        body = (directory / "raw" / page["file"]).read_bytes()
        if hashlib.sha256(body).hexdigest() != page["sha256"]:
            raise ValueError("Raw file changed: " + page["file"])
        hdfs.put(path + "/" + page["file"], body)
    manifest["hdfs_complete"] = True
    manifest["hdfs_raw_path"] = path
    hdfs.put(path + "/_manifest.json", json.dumps(manifest).encode("utf-8"))
    save_json(directory / "raw_manifest.json", manifest)
    LOG.info("Raw snapshot uploaded: %s", path)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-pages", type=int, default=0)
    parser.add_argument("--download-only", action="store_true", help="Only stage locally; does not complete the HDFS step")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    fetch(args.run_id, args.max_pages, args.download_only)


if __name__ == "__main__":
    main()
