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

# `from .settings import *` runs config/settings.py in full first (its
# own load_dotenv() call picks up your normal .env), which is why every
# setting NOT explicitly overridden below — INSTALLED_APPS, MIDDLEWARE,
# REST_FRAMEWORK, SIMPLE_JWT, etc. — stays identical to production.
from .settings import *  # noqa: F401,F403  (reuse INSTALLED_APPS, REST_FRAMEWORK, etc.)
from .settings import BASE_DIR

# override=True is required here: settings.py already called
# load_dotenv() for the default .env above, which may have populated
# some of the same-named env vars in os.environ. Without override=True,
# python-dotenv would refuse to overwrite them and .env.test would be
# silently ignored.
load_dotenv(BASE_DIR / ".env.test", override=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        # Falls back to the same defaults as docker-compose.test.yml if
        # .env.test is missing a key, so `pytest` still works even
        # without a fully-filled-in .env.test file.
        "NAME": os.environ.get("TEST_DB_NAME", "inventra_test"),
        "USER": os.environ.get("TEST_DB_USER", "inventra_test"),
        "PASSWORD": os.environ.get("TEST_DB_PASSWORD", "inventra_test"),
        "HOST": os.environ.get("TEST_DB_HOST", "localhost"),
        "PORT": os.environ.get("TEST_DB_PORT", "5433"),
    }
}

# otp_services.py builds its Redis client from settings.REDIS_URL at
# IMPORT time (not lazily) — so this override only works because
# settings_test.py is fully loaded and active before any test module
# imports otp_services. pytest-django guarantees that ordering.
REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/0")

# Password hashing is the single slowest part of creating test users by
# the hundreds (UserFactory calls set_password/set_unusable_password on
# every generated user). MD5 is drastically faster than Django's default
# PBKDF2 and is fine here since these are throwaway test users that will
# never exist outside a test run, never real production accounts.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
