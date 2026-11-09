import logging
import os
import json

from flask import Flask, jsonify, render_template, request
import pymysql

from scripts.common import connect_database

app = Flask(__name__)


def escaped_like(value):
    return "%" + value.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


@app.get("/")
def index():
    query = request.args.get("q", "").strip()
    error = None
    status = 200
    cards = []
    count = 0
    limited = False
    if len(query) > 200:
        error, status = "Bitte höchstens 200 Zeichen eingeben.", 400
    else:
        try:
            connection = connect_database(test=os.environ.get("MTG_WEB_TEST_DATABASE") == "1", dictionary=True)
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) AS total FROM cards")
                    count = cursor.fetchone()["total"]
                    if query:
                        cursor.execute(
                            "SELECT id,multiverseid,name,card_text,artist,set_code,image_url FROM cards "
                            "WHERE LOWER(name) LIKE LOWER(%s) ESCAPE '!' "
                            "OR LOWER(card_text) LIKE LOWER(%s) ESCAPE '!' "
                            "OR LOWER(artist) LIKE LOWER(%s) ESCAPE '!' ORDER BY name,id LIMIT 51",
                            (escaped_like(query),) * 3,
                        )
                        result = cursor.fetchall()
                        limited = len(result) > 50
                        cards = result[:50]
            finally:
                connection.close()
        except pymysql.MySQLError:
            app.logger.exception("Database query failed")
            error, status = "Die Kartensuche ist gerade nicht erreichbar. Bitte später erneut versuchen.", 503
    return render_template("index.html", cards=cards, query=query,
                           count=count, limited=limited, error=error), status


@app.get("/health")
def health():
    try:
        connection = connect_database()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM cards LIMIT 1")
        finally:
            connection.close()
        return {"status": "ok"}
    except pymysql.MySQLError:
        return {"status": "unavailable"}, 503


@app.get("/cards/<path:card_id>")
def card_details(card_id):
    if len(card_id) > 128:
        return jsonify(message="Ungültige Karten-ID."), 400
    try:
        connection = connect_database(test=os.environ.get("MTG_WEB_TEST_DATABASE") == "1", dictionary=True)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT details_json FROM cards WHERE id=%s", (card_id,))
                row = cursor.fetchone()
        finally:
            connection.close()
        if row is None or not row["details_json"]:
            return jsonify(message="Keine weiteren Kartendaten verfügbar."), 404
        return jsonify(card=json.loads(row["details_json"]))
    except (pymysql.MySQLError, ValueError):
        app.logger.exception("Card details unavailable")
        return jsonify(message="Die Kartendaten sind gerade nicht erreichbar. Bitte erneut versuchen."), 503


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=5000, debug=False)
