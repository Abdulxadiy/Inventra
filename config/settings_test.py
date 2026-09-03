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
from pathlib import Path

from dotenv import load_dotenv

# IMPORTANT ORDERING: .env.test must be loaded BEFORE `from .settings
# import *` runs below. config/settings.py reads several env vars with
# NO fallback default at module level (e.g.
# `ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS").split(",")`), so if those
# vars aren't already in os.environ by the time settings.py executes,
# Django crashes at import time with something like:
#   AttributeError: 'NoneType' object has no attribute 'split'
# We can't call `from .settings import BASE_DIR` first and load_dotenv()
# afterwards (that was the bug in an earlier version of this file) —
# by then settings.py has ALREADY run and already crashed. So BASE_DIR
# is computed independently here, the same way settings.py computes it,
# purely so we can find .env.test before settings.py is ever imported.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env.test", override=True)

# NOW it's safe to import settings.py: every env var it needs already
# exists in os.environ, either from .env.test above or from whatever
# was already in the shell environment. Its own internal `load_dotenv()`
# call (for the default .env) runs WITHOUT override=True, so it can't
# clobber the .env.test values we just set.
from .settings import *  # noqa: F401,F403  (reuse INSTALLED_APPS, REST_FRAMEWORK, etc.)

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
