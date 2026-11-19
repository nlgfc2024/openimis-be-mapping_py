"""Portable schema tests; does not import a CoreMIS assembly or adapter models."""
import unittest
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        SECRET_KEY="mapping-unit-tests-only",
        INSTALLED_APPS=[],
        DATABASES={"default":{"ENGINE":"django.db.backends.sqlite3","NAME":":memory:"}},
    )
django.setup()

if __name__ == "__main__":
    unittest.main(module="mapping.tests.test_schema", verbosity=2)
