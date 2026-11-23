from unittest import TestCase
from types import SimpleNamespace
from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from mapping.apps import MappingConfig

class CapabilityTests(TestCase):
    def test_view_permission_does_not_grant_project_access(self):
        from mapping.access import require_capability
        user = SimpleNamespace(is_anonymous=False, has_perms=lambda rights: rights == ["view"])
        with patch.multiple(MappingConfig, enabled=True, view_perms=["view"], project_perms=["project"]):
            require_capability(user, "view_perms")
            with self.assertRaises(PermissionDenied):
                require_capability(user, "project_perms")

    def test_empty_rights_are_denied(self):
        from mapping.access import require_capability
        with patch.multiple(MappingConfig, enabled=True, project_perms=[]):
            with self.assertRaises(PermissionDenied):
                require_capability(SimpleNamespace(is_anonymous=False, has_perms=lambda rights: True), "project_perms")


class ImportBoundaryTests(TestCase):
    def test_mapping_runtime_has_no_importer_or_http_dependency(self):
        import ast
        from pathlib import Path
        import mapping
        for path in Path(mapping.__file__).parent.rglob('*.py'):
            if any(part in ('tests','migrations','__pycache__') for part in path.parts):
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                names = [node.module or ''] if isinstance(node,ast.ImportFrom) else [item.name for item in node.names] if isinstance(node,ast.Import) else []
                self.assertFalse(any(name.split('.')[0] in ('msr_etl','requests','httpx') for name in names),str(path))
        from mapping.schema import Query
        self.assertNotIn('mapping_start_sync',Query._meta.fields)
        self.assertNotIn('mapping_sync_run',Query._meta.fields)
