"""Keep offline tests isolated from local account configuration."""
import os
from tempfile import TemporaryDirectory

_TEST_DATA = TemporaryDirectory(prefix="reeftrace-tests-")
os.environ["REEFTRACE_DATA_DIR"] = _TEST_DATA.name
os.environ["REEFTRACE_DB_PATH"] = _TEST_DATA.name + "/legacy.sqlite3"

os.environ["DATABASE_URL"] = ""
os.environ["GEMINI_ENABLED"] = "false"
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
os.environ["PHOTON_ENABLED"] = "false"
os.environ["PHOTON_ROUTES_JSON"] = "[]"
