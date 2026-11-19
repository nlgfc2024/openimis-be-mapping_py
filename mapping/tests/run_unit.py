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
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in
        ("mapping.tests.test_schema", "mapping.tests.test_provider"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
