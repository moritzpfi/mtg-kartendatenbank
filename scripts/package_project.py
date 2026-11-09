"""Build the source hand-in without credentials, generated data, or local environments."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parent.parent
    target = root / "abgabe" / "MTG_API_Abgabe.zip"
    target.parent.mkdir(exist_ok=True)
    excluded = {".git", ".venv", "__pycache__", "work", "abgabe", ".pytest_cache"}
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if path.is_file() and not excluded.intersection(relative.parts) and path.name != ".env":
                archive.write(path, relative.as_posix())
    print(target)


if __name__ == "__main__":
    main()
