"""Generate a private local .env once; never print its secrets."""

import base64
from pathlib import Path
import secrets


def main():
    root = Path(__file__).resolve().parent.parent
    target = root / ".env"
    if target.exists():
        print(".env already exists; preserved.")
        return
    text = (root / ".env.example").read_text(encoding="utf-8")
    for key in ("MYSQL_ROOT_PASSWORD", "MYSQL_PASSWORD", "AIRFLOW_ADMIN_PASSWORD"):
        text = text.replace(key + "=\n", key + "=" + secrets.token_urlsafe(32) + "\n")
    text = text.replace("AIRFLOW_FERNET_KEY=\n", "AIRFLOW_FERNET_KEY=" +
                        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode() + "\n")
    text += "AIRFLOW_WEBSERVER_SECRET_KEY=" + secrets.token_hex(32) + "\n"
    target.write_text(text, encoding="utf-8")
    target.chmod(0o600)
    print("Created private .env with generated passwords. Airflow user: admin.")


if __name__ == "__main__":
    main()
