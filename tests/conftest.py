import pytest
import tempfile
import os
import sys

# Ensure root directory is on search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
import database


@pytest.fixture(scope="session")
def app():
    """Session-wide test Flask application with isolated test database."""
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db_path = temp_db.name
    temp_db.close()

    test_config = {
        "TESTING": True,
        "DATABASE_PATH": temp_db_path,
        "SECRET_KEY": "test-suite-secure-ephemeral-key-9999",
        "EXECUTION_TIMEOUT": 15.0,
        "MAX_CODE_LENGTH": 50000,
        "DEFAULT_AI_PROVIDER": "offline"
    }

    # Set database path in Config module
    database.Config.DATABASE_PATH = temp_db_path
    database.init_db()

    application = create_app(test_config)

    yield application

    # Cleanup temp database
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except Exception:
            pass


@pytest.fixture
def client(app):
    """Test client for exercising HTTP endpoints."""
    return app.test_client()
