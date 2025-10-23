# pylint: skip-file
# flake8: noqa
"""
Django settings for running tests.

This settings module overrides certain production settings to ensure that
tests run quickly, safely, and without side effects. In particular, it sets
DEFAULT_FILE_STORAGE to use DummyStorage so that no files are written to disk
or external services during tests.

Usage:
    Set DJANGO_SETTINGS_MODULE=project.settings_test when running tests,
    or configure pytest.ini accordingly.

Note:
    Linting is disabled for this file to avoid warnings about unused imports
    or test-specific overrides.
"""
from .settings import *

STORAGES = {
    "default": {
        "BACKEND": "core_directory.storages.dummy_storage.DummyStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
