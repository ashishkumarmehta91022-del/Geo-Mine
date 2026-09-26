"""Configuration and database URL composition tests (no PostgreSQL required)."""

from app.config import Settings


def test_database_url_composed_from_discrete_variables():
    s = Settings(
        database_url="",
        db_host="db.example.test",
        db_port=5433,
        db_name="test_db",
        db_user="test_user",
        db_password="p@ss w0rd:",  # specials must be URL-encoded
    )
    url = s.effective_database_url
    assert url == "postgresql://test_user:p%40ss%20w0rd%3A@db.example.test:5433/test_db"


def test_explicit_database_url_takes_precedence():
    s = Settings(
        database_url="postgresql://u:p@explicit-host:5432/explicit_db",
        db_host="ignored-host",
        db_user="ignored_user",
    )
    assert s.effective_database_url == "postgresql://u:p@explicit-host:5432/explicit_db"


def test_defaults_allow_startup_without_environment():
    s = Settings(database_url="", db_password="")
    assert s.db_host == "localhost"
    assert s.db_port == 5432
    assert s.db_name == "cmpdi_reporting"
    assert s.db_user == "cmpdi_user"
