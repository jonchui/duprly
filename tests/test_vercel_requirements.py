"""The Vercel function installs only api/requirements.txt.

Every third-party module imported by code the function loads must be listed there,
or the route 500s in production with ModuleNotFoundError (court DUPR sign-in, #64).
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILES = ["dupr_client.py", "dupr_rate_limit.py", *map(str, (ROOT / "web").rglob("*.py"))]
LOCAL = {p.stem for p in ROOT.glob("*.py")} | {"web", "api", "tests"}
# import name -> pip name, where they differ
PIP = {"psycopg": "psycopg", "dotenv": "python-dotenv", "multipart": "python-multipart", "yaml": "pyyaml"}
OPTIONAL = {"urllib3", "dotenv", "numpy", "scipy", "sklearn"}  # guarded by try/except or not on the web path


def _top_imports(path):
    tree = ast.parse(pathlib.Path(path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0]


def test_api_requirements_cover_imports():
    listed = set()
    for line in (ROOT / "api" / "requirements.txt").read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            listed.add(line.split("[")[0].split(">")[0].split("=")[0].split("<")[0].strip().lower())
    missing = set()
    for f in FILES:
        for mod in _top_imports(ROOT / f if not f.startswith("/") else f):
            if mod in sys.stdlib_module_names or mod in LOCAL or mod in OPTIONAL:
                continue
            if PIP.get(mod, mod).lower() not in listed:
                missing.add(f"{mod} ({pathlib.Path(f).name})")
    assert not missing, f"add to api/requirements.txt: {sorted(missing)}"
