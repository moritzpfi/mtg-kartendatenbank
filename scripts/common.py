"""Shared configuration and the two external storage connections."""

import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlsplit, urlunsplit

import pymysql
import requests


def normalize_image_url(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = urlsplit(value.strip())
        if (parsed.scheme not in ("http", "https")
                or parsed.hostname not in ("gatherer.wizards.com", "gatherer-static.wizards.com")
                or parsed.username or parsed.password or parsed.port not in (None, 80, 443)):
            return None
        return urlunsplit(("https", parsed.hostname, parsed.path, parsed.query, ""))
    except ValueError:
        return None


def run_directory(run_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", run_id):
        raise ValueError("run-id must contain 1-100 ASCII letters, digits, _ or -")
    path = Path(os.environ.get("WORK_DIR", "work")) / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def connect_database(test=False, dictionary=False):
    return pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "mysql"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", "mtg"),
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ.get("MYSQL_TEST_DATABASE", "mtg_test") if test
        else os.environ.get("MYSQL_DATABASE", "mtg"),
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=15,
        read_timeout=120,
        write_timeout=120,
        cursorclass=pymysql.cursors.DictCursor if dictionary else pymysql.cursors.Cursor,
    )


class Hdfs:
    """WebHDFS client."""

    def __init__(self):
        self.url = os.environ.get("HDFS_URL", "http://hdfs:9870").rstrip("/")
        self.root = os.environ.get("HDFS_ROOT", "/user/hadoop/mtg").rstrip("/")
        self.user = os.environ.get("HDFS_USER", "root")
        self.session = requests.Session()

    def request(self, method, path, operation, **kwargs):
        parameters = {"op": operation, "user.name": self.user}
        parameters.update(kwargs.pop("params", {}))
        response = self.session.request(
            method, self.url + "/webhdfs/v1" + quote(path, safe="/"),
            params=parameters, timeout=(15, 120), **kwargs,
        )
        response.raise_for_status()
        return response

    def mkdir(self, path):
        result = self.request("PUT", path, "MKDIRS").json()
        if result.get("boolean") is not True:
            raise RuntimeError("HDFS did not create " + path)

    def put(self, path, data):
        # WebHDFS CREATE redirects from the NameNode to a DataNode.
        response = self.request("PUT", path, "CREATE", allow_redirects=False,
                                params={"overwrite": "true"})
        if response.status_code != 307:
            raise RuntimeError("Expected a WebHDFS DataNode redirect")
        result = self.session.put(response.headers["Location"], data=data, timeout=(15, 120))
        result.raise_for_status()
        if result.status_code != 201:
            raise RuntimeError("HDFS did not confirm file creation")

    def read(self, path):
        return self.request("GET", path, "OPEN").content

    def list(self, path):
        return self.request("GET", path, "LISTSTATUS").json()["FileStatuses"]["FileStatus"]
