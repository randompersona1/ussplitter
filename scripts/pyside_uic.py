"""Create python files from Qt Designer .ui files."""

from pathlib import Path
from subprocess import run

FORMS_PATH = "src/ussplitter/forms"


def main():
    for file in Path(FORMS_PATH).rglob("*.ui"):
        run(["pyside6-uic", str(file), "-o", str(file.with_suffix(".py"))], check=True)


if __name__ == "__main__":
    main()
