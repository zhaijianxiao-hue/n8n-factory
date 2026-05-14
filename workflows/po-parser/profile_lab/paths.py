from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
PO_PARSER_DIR = PACKAGE_DIR.parent
DEFAULT_LAB_ROOT = PO_PARSER_DIR / "profile-lab"
SCHEMA_PATH = PO_PARSER_DIR / "schemas" / "po-output.schema.json"
PRODUCTION_PROFILE_DIR = PO_PARSER_DIR / "profiles"
