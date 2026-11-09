"""Transform the HDFS snapshot with PySpark, validate it, and publish to MySQL."""

import argparse
import hashlib
from itertools import islice
import json
import logging
import os
from pathlib import Path

from scripts.common import Hdfs, connect_database, normalize_image_url, run_directory, save_json
from scripts.data_quality import audit_raw, write_quality_report
from scripts.text_cleaning import clean_card

LOG = logging.getLogger(__name__)
COLUMNS = ("id", "multiverseid", "name", "card_text", "artist", "set_code", "image_url", "source_json", "details_json")


def canonical_cards(page_bytes):
    """Keep every source property, including nested and previously unknown fields."""
    page = json.loads(bytes(page_bytes).decode("utf-8"))
    return [json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for card in page["cards"]]


def spark_session():
    from pyspark.sql import SparkSession
    os.environ.setdefault("PYSPARK_SUBMIT_ARGS", "--driver-memory 2g pyspark-shell")
    return (SparkSession.builder.master(os.environ.get("SPARK_MASTER", "local[2]"))
            .appName("MTG cards").config("spark.ui.enabled", "false")
            .config("spark.sql.shuffle.partitions", "8")
            .config("spark.sql.adaptive.coalescePartitions.enabled", "false")
            .config("spark.ui.showConsoleProgress", "false")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.hadoop.dfs.replication", "1")
            .config("spark.hadoop.fs.defaultFS", os.environ.get("HDFS_FS_URI", "hdfs://hdfs:8020"))
            .getOrCreate())


def digest_rows(rows):
    """Hash ordered canonical rows identically in Spark and MySQL."""
    digest = hashlib.sha256()
    for row in rows:
        digest.update((json.dumps(list(row), ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
    return digest.hexdigest()


def transform(run_id):
    from pyspark.sql import functions as F
    from pyspark.sql.types import ArrayType, StringType, StructField, StructType

    hdfs = Hdfs()
    manifest = json.loads(hdfs.read(f"{hdfs.root}/raw/{run_id}/_manifest.json"))
    if not manifest.get("download_complete") or not manifest.get("hdfs_complete"):
        raise ValueError("Raw snapshot has not been completed in HDFS")
    quality = audit_raw(hdfs, manifest)
    unexpected_types = [field for field, counts in quality["fields"].items()
                        if field != "multiverseid" and counts.get("non_string", 0)]
    if unexpected_types:
        raise ValueError("Unexpected raw field types; inspect data_quality.json: " + ", ".join(unexpected_types))
    spark = spark_session()
    spark.sparkContext.setLogLevel("WARN")
    try:
        card_schema = StructType([StructField(name, StringType())
                                  for name in ("id", "multiverseid", "name", "text", "artist", "set", "imageUrl")])
        files = [f"{hdfs.root}/raw/{run_id}/{page['file']}" for page in manifest["pages"]]
        originals = (spark.read.format("binaryFile").load(files)
                     .select(F.explode(F.udf(canonical_cards, ArrayType(StringType()))("content")).alias("source_json")))
        raw = (originals.select(F.from_json("source_json", card_schema, {"mode": "FAILFAST"}).alias("card"), "source_json")
               .select("card.*", "source_json").cache())
        raw_count = raw.count()
        if raw_count != manifest["raw_count"]:
            raise ValueError("Parsed count differs from the raw download manifest")
        valid = (raw.filter(F.col("id").isNotNull() & (F.length(F.trim("id")) > 0)
                            & F.col("name").isNotNull() & (F.length(F.trim("name")) > 0))
                 .select(F.trim("id").alias("id"),
                         F.when(F.col("multiverseid").rlike(r"^[0-9]+$"),
                                F.col("multiverseid").cast("long")).alias("multiverseid"),
                         F.trim("name").alias("name"),
                         F.coalesce("text", F.lit("")).alias("card_text"),
                         F.coalesce("artist", F.lit("")).alias("artist"),
                         F.coalesce("set", F.lit("")).alias("set_code"),
                         F.udf(normalize_image_url, StringType())("imageUrl").alias("image_url"),
                         F.col("source_json"),
                         F.udf(cleaned_json, StringType())("source_json").alias("details_json")).cache())
        valid_count = valid.count()
        unique = valid.dropDuplicates(list(COLUMNS)).cache()
        conflicts = unique.groupBy("id").count().filter(F.col("count") > 1).limit(1).count()
        if conflicts:
            raise ValueError("Conflicting records for one API id; nothing published")
        if unique.filter((F.length("id") > 128) | (F.length("set_code") > 32)).limit(1).count():
            raise ValueError("API value exceeds the documented database schema")
        final_count = unique.count()
        raw.unpersist()
        valid.unpersist()
        if not final_count:
            raise ValueError("Empty final snapshot is not publishable")
        final_counts = unique.agg(
            F.sum((F.length("card_text") == 0).cast("long")).alias("empty_card_text"),
            F.sum((F.length("artist") == 0).cast("long")).alias("empty_artist"),
            F.sum(F.col("multiverseid").isNull().cast("long")).alias("null_multiverseid"),
            F.sum(F.col("image_url").isNotNull().cast("long")).alias("with_image_url"),
            F.sum(F.col("image_url").isNull().cast("long")).alias("without_image_url"),
        ).first().asDict()
        if raw_count == valid_count == final_count:
            changes = quality["changes"]
            expected_counts = {
                "empty_card_text": changes.get("missing_text_to_empty", 0) + quality["fields"]["text"].get("empty_string", 0),
                "empty_artist": changes.get("missing_artist_to_empty", 0) + quality["fields"]["artist"].get("empty_string", 0),
                "null_multiverseid": changes.get("multiverseid_missing", 0) + changes.get("multiverseid_invalid_to_null", 0),
                "with_image_url": changes.get("image_url_available", 0),
                "without_image_url": final_count - changes.get("image_url_available", 0),
            }
            if final_counts != expected_counts:
                raise ValueError("Final field counts differ from independent raw audit")
        path = f"{hdfs.root}/final/{run_id}"
        unique.write.mode("overwrite").parquet(path)
        unique.unpersist(blocking=True)
        written = spark.read.parquet(path).select(*COLUMNS)
        checksum = digest_rows(written.orderBy("id").toLocalIterator())
        summary = {
            "run_id": run_id, "development": manifest["development"],
            "source": manifest["source"], "source_total_counts": manifest["total_counts"],
            "source_pages": len(manifest["pages"]), "raw_count": raw_count,
            "invalid_count": raw_count - valid_count, "duplicate_count": valid_count - final_count,
            "final_count": final_count, "sha256": checksum, "hdfs_final_path": path,
            "completeness_note": "Development subset; not a full source snapshot" if manifest["development"]
            else manifest.get("completeness_note", "Total-Count matched"),
            "data_quality": quality,
            "text_cleaning": quality["text_cleaning"],
            "final_field_counts": final_counts,
            "export_columns": list(COLUMNS),
        }
        hdfs.put(path + "/_summary.json", json.dumps(summary).encode("utf-8"))
        save_json(run_directory(run_id) / "final_summary.json", summary)
        LOG.info("Final snapshot: %s", summary)
        return summary
    finally:
        spark.stop()


def cleaned_json(source_json):
    card, _, _ = clean_card(json.loads(source_json))
    return json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def final_data(spark, run_id):
    hdfs = Hdfs()
    path = f"{hdfs.root}/final/{run_id}"
    summary = json.loads(hdfs.read(path + "/_summary.json"))
    data = spark.read.parquet(path).select(*COLUMNS)
    count = data.count()
    if data.filter(data.details_json.isNull()).limit(1).count():
        raise ValueError("Final snapshot is missing cleaned detail objects")
    checksum = digest_rows(data.orderBy("id").toLocalIterator())
    if count != summary["final_count"] or checksum != summary["sha256"]:
        raise ValueError("Final Parquet data does not match its summary")
    if count + summary["invalid_count"] + summary["duplicate_count"] != summary["raw_count"]:
        raise ValueError("Raw/final accounting does not add up")
    return summary, data


def ensure_schema(connection):
    root = Path(__file__).resolve().parent.parent
    with connection.cursor() as cursor:
        for table in ("cards", "cards_staging"):
            cursor.execute((root / "sql" / (table + ".sql")).read_text(encoding="utf-8"))
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE 'image_url'")
            if cursor.fetchone() is None:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN image_url TEXT NULL")
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE 'source_json'")
            if cursor.fetchone() is None:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN source_json MEDIUMTEXT NULL")
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE 'details_json'")
            if cursor.fetchone() is None:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN details_json MEDIUMTEXT NULL")
    connection.commit()


def database_summary(connection, table="cards"):
    import pymysql
    if table not in ("cards", "cards_staging"):
        raise ValueError("Unknown table")
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
    with connection.cursor(pymysql.cursors.SSCursor) as cursor:
        cursor.execute(f"SELECT {','.join(COLUMNS)} FROM {table} ORDER BY id")
        checksum = digest_rows(cursor)
    return {"count": count, "sha256": checksum}


def database_field_counts(connection, table="cards"):
    if table not in ("cards", "cards_staging"):
        raise ValueError("Unknown table")
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT SUM(CHAR_LENGTH(card_text)=0),SUM(CHAR_LENGTH(artist)=0),"
                       f"SUM(multiverseid IS NULL),SUM(image_url IS NOT NULL),SUM(image_url IS NULL) FROM {table}")
        values = cursor.fetchone()
    return dict(zip(("empty_card_text", "empty_artist", "null_multiverseid", "with_image_url", "without_image_url"),
                    (int(value or 0) for value in values)))


def publish_snapshot(connection, rows, expected, fail_after_delete=False):
    """Only the final DELETE/INSERT transaction can change the searchable snapshot."""
    try:
        with connection.cursor() as cursor:
            while cursor.execute("DELETE FROM cards_staging LIMIT 1000"):
                pass
            iterator = iter(rows)
            while batch := list(islice(iterator, 1000)):
                cursor.executemany(
                    f"INSERT INTO cards_staging ({','.join(COLUMNS)}) VALUES ({','.join(['%s'] * len(COLUMNS))})",
                    [tuple(row) for row in batch],
                )
        staged = database_summary(connection, "cards_staging")
        if staged != {"count": expected["final_count"], "sha256": expected["sha256"]}:
            raise ValueError("Staging contents do not match the final snapshot")
        if "final_field_counts" in expected and database_field_counts(connection, "cards_staging") != expected["final_field_counts"]:
            raise ValueError("Staging field counts differ from final snapshot")
        connection.commit()
        connection.begin()
        with connection.cursor() as cursor:
            while cursor.execute("DELETE FROM cards LIMIT 1000"):
                pass
            if fail_after_delete:
                raise RuntimeError("Intentional rollback test after DELETE")
            last_id = ""
            copied = 0
            while True:
                cursor.execute(f"INSERT INTO cards ({','.join(COLUMNS)}) SELECT {','.join(COLUMNS)} "
                               "FROM cards_staging WHERE id>%s ORDER BY id LIMIT 1000", (last_id,))
                if not cursor.rowcount:
                    break
                copied += cursor.rowcount
                cursor.execute("SELECT MAX(id) FROM cards")
                last_id = cursor.fetchone()[0]
                if copied % 10000 == 0 or copied == expected["final_count"]:
                    LOG.info("Published within transaction: %s/%s cards", copied, expected["final_count"])
        published = database_summary(connection)
        if published != staged:
            raise ValueError("Published database contents do not match staging")
        if "final_field_counts" in expected and database_field_counts(connection) != expected["final_field_counts"]:
            raise ValueError("Published field counts differ from final snapshot")
        connection.commit()
        return published
    except Exception:
        if connection.open:
            connection.rollback()
        raise


def process(action, run_id, test_database=False, fail_after_delete=False):
    run_directory(run_id)  # Validate the identifier before using it in HDFS paths.
    if action == "transform":
        return transform(run_id)
    spark = spark_session()
    spark.sparkContext.setLogLevel("WARN")
    try:
        summary, data = final_data(spark, run_id)
        if action == "validate-final":
            LOG.info("Final snapshot validated: %s", summary)
            return summary
        if summary["development"] and not test_database:
            raise ValueError("Development snapshots may only be loaded into the test database")
        if fail_after_delete and not test_database:
            raise ValueError("Failure injection is restricted to the test database")
        connection = connect_database(test=test_database)
        try:
            ensure_schema(connection)
            if action == "load":
                actual = publish_snapshot(connection, data.orderBy("id").toLocalIterator(),
                                          summary, fail_after_delete)
            else:
                actual = database_summary(connection)
                if actual != {"count": summary["final_count"], "sha256": summary["sha256"]}:
                    raise ValueError("Database does not match the final snapshot")
            result = {"run_id": run_id, "test_database": test_database, **actual}
            result["field_counts"] = database_field_counts(connection)
            if result["field_counts"] != summary["final_field_counts"]:
                raise ValueError("Database field counts differ from final snapshot")
            save_json(run_directory(run_id) / "database_summary.json", result)
            write_quality_report(summary, result)
            LOG.info("Database %s: %s", action, result)
            return result
        finally:
            connection.close()
    finally:
        spark.stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("transform", "validate-final", "load", "validate-database"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--test-database", action="store_true")
    parser.add_argument("--fail-after-delete", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    process(args.action, args.run_id, args.test_database, args.fail_after_delete)


if __name__ == "__main__":
    main()
