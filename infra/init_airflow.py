import os
import subprocess

from scripts.common import connect_database
from scripts.process_cards import ensure_schema

subprocess.run(["airflow", "db", "migrate"], check=True)
from airflow.www.app import create_app

application = create_app()
with application.app_context():
    security = application.appbuilder.sm
    if not security.find_user(username="admin"):
        security.add_user(username="admin", first_name="MTG", last_name="Admin",
                          email="admin@localhost.invalid", role=security.find_role("Admin"),
                          password=os.environ["AIRFLOW_ADMIN_PASSWORD"])
for test in (False, True):
    connection = connect_database(test=test)
    try:
        ensure_schema(connection)
    finally:
        connection.close()
print("Airflow and both application schemas initialized.")
