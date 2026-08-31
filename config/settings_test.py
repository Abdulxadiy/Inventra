"""
Test-only settings. Reuses everything from config/settings.py and only
overrides what needs to point at the isolated test infrastructure
(docker-compose.test.yml): a separate Postgres and a separate Redis,
so pytest never touches your dev/production database or cache.

Place at: config/settings_test.py

Wire it up in pytest.ini:
    DJANGO_SETTINGS_MODULE = config.settings_test
"""
import os

from dotenv import load_dotenv

from .settings import *  # noqa: F401,F403  (reuse INSTALLED_APPS, REST_FRAMEWORK, etc.)
from .settings import BASE_DIR

# .env.test intentionally overrides anything the base settings.py already
# loaded from .env — copy .env.test.example to .env.test and adjust.
load_dotenv(BASE_DIR / ".env.test", override=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ.get("TEST_DB_NAME", "inventra_test"),
        "USER": os.environ.get("TEST_DB_USER", "inventra_test"),
        "PASSWORD": os.environ.get("TEST_DB_PASSWORD", "inventra_test"),
        "HOST": os.environ.get("TEST_DB_HOST", "localhost"),
        "PORT": os.environ.get("TEST_DB_PORT", "5433"),
    }
}

REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/0")

# Password hashing is the single slowest part of creating test users by the
# hundreds (UserFactory calls set_password/set_unusable_password a lot).
# MD5 is fine here since these are throwaway test users, never real ones.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
