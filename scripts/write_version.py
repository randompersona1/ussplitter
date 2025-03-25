import tomllib

PYPROJECT_RELATIVE_PATH = "pyproject.toml"
VERSION_FILE_RELATIVE_PATH = "src/ussplitter/_version.py"


def write_version():
    with open(PYPROJECT_RELATIVE_PATH) as f:
        pyproject = tomllib.loads(f.read())
    version = pyproject["project"]["version"]

    with open(VERSION_FILE_RELATIVE_PATH, "w") as f:
        f.write(f'__version__ = "{version}"\n')


if __name__ == "__main__":
    write_version()
