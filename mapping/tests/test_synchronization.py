"""Host contract tests. Run with the isolated-schema runner, never production tables."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
import uuid

from django.core.exceptions import PermissionDenied
from django.db import transaction

from mapping.apps import MappingConfig
from mapping.configuration import configuration_fingerprint
from mapping.models import MappingSyncState
from mapping.synchronization import apply_unit, prepare_receipt, SnapshotRejected


class SynchronizationTests(TestCase):
    def setUp(self):
        self.atomic = transaction.atomic()
        self.atomic.__enter__()
        self.addCleanup(self.rollback)
        self.config = {"source_instance": "fixture", "base_url": "http://localhost:8080", "auth_bearer_token": "fixture"}
        for patcher in (
            patch("mapping.synchronization.refresh_configuration"),
            patch("mapping.synchronization.current_source", side_effect=lambda receipt: deepcopy(self.config)),
            patch("mapping.synchronization.require_district_scope"),
            patch("location.msr_reference.MsrReferenceWriter"),
        ):
            value = patcher.start()
            self.addCleanup(patcher.stop)
            if patcher.attribute == "MsrReferenceWriter":
                self.writer = value.return_value
            if patcher.attribute == "require_district_scope":
                self.scope = value

    def rollback(self):
        transaction.set_rollback(True)
        self.atomic.__exit__(None, None, None)

    def unit(self, pk):
        source = SimpleNamespace(policy="legacy", source_type="msr_geo_v3", source_instance="fixture", district_id=13,
                                 client=SimpleNamespace(config=self.config))
        unit = SimpleNamespace(pk=pk, job_uuid=uuid.uuid4(), source_type="msr_geo_v3", unit_code="13")
        unit.raw_payload = {"source_instance": "fixture", "locations": [{"id": 13, "type": "districts", "district_id": 13}],
                            "memberships": [], "_mapping": prepare_receipt(source, unit)}
        return unit

    def test_newer_snapshot_prevents_older_overwrite(self):
        older, newer = self.unit(10), self.unit(20)
        self.assertEqual(apply_unit(newer, None), 1)
        with self.assertRaisesRegex(SnapshotRejected, "STALE"):
            apply_unit(older, None)
        self.writer.push.assert_called_once()
        self.assertEqual(MappingSyncState.objects.get().last_applied_unit_id, 20)

    def test_replaying_same_unit_is_idempotent(self):
        unit = self.unit(10)
        apply_unit(unit, None)
        apply_unit(unit, None)
        self.writer.push.assert_called_once()

    def test_membership_failure_rolls_back_ordering_state(self):
        self.writer.replace_memberships.side_effect = ValueError("fixture failure")
        with self.assertRaises(ValueError):
            apply_unit(self.unit(10), None)
        self.assertFalse(MappingSyncState.objects.exists())

    def test_config_rotation_requires_new_snapshot(self):
        unit = self.unit(10)
        self.config["auth_bearer_token"] = "rotated-fixture"
        with self.assertRaisesRegex(SnapshotRejected, "CONFIG_CHANGED"):
            apply_unit(unit, None)
        self.writer.push.assert_not_called()

    def test_config_rechecked_after_lock(self):
        unit = self.unit(10)
        with patch("mapping.synchronization.current_source", side_effect=[self.config, {**self.config, "base_url": "http://localhost:8081"}]):
            with self.assertRaisesRegex(SnapshotRejected, "CONFIG_CHANGED"):
                apply_unit(unit, None)
        self.writer.push.assert_not_called()
        self.assertFalse(MappingSyncState.objects.exists())

    def test_revoked_scope_rechecked_after_lock(self):
        self.scope.side_effect = [None, PermissionDenied("revoked")]
        with self.assertRaises(PermissionDenied):
            apply_unit(self.unit(10), None)
        self.writer.push.assert_not_called()
        self.assertFalse(MappingSyncState.objects.exists())

    def test_missing_receipt_cannot_use_legacy_fallback(self):
        unit = self.unit(10)
        del unit.raw_payload["_mapping"]
        with self.assertRaisesRegex(SnapshotRejected, "RESTAGE"):
            apply_unit(unit, None)

    def test_missing_membership_snapshot_cannot_clear_existing_coverage(self):
        unit = self.unit(10)
        unit.raw_payload["locations"].append({"id": 265, "type": "catchments", "district_id": 13, "is_micro": True})
        with self.assertRaisesRegex(SnapshotRejected, "INCOMPLETE_MEMBERSHIPS"):
            apply_unit(unit, None)
        self.writer.push.assert_not_called()

    def test_village_cannot_be_in_two_catchments(self):
        unit = self.unit(10)
        unit.raw_payload["locations"] += [{"id": i, "type": "catchments", "district_id": 13, "is_micro": True} for i in (1, 2)]
        unit.raw_payload["locations"].append({"id": 88, "type": "villages", "district_id": 13})
        unit.raw_payload["memberships"] = [{"catchment_id": i, "village_ids": [88]} for i in (1, 2)]
        with self.assertRaisesRegex(SnapshotRejected, "CONFLICT"):
            apply_unit(unit, None)
        self.writer.push.assert_not_called()

    def test_fingerprint_contains_no_credential_and_changes_with_scope(self):
        with patch.object(MappingConfig, "permitted_district_ids", [13]):
            before = configuration_fingerprint(self.config, "mapping")
        with patch.object(MappingConfig, "permitted_district_ids", [14]):
            after = configuration_fingerprint(self.config, "mapping")
        self.assertNotEqual(before, after)
        self.assertEqual(len(before), 64)
        self.assertNotIn("fixture", before)

    def test_schedule_uses_core_job_only_after_commit(self):
        from django.test import TestCase as DjangoTestCase
        from mapping.jobs import start_sync
        actor = Mock()
        with patch("mapping.jobs.refresh_configuration"), patch("mapping.jobs.resolve_district", return_value=13), \
             patch("mapping.jobs.require_district_scope"), patch("mapping.jobs.provider_for"), \
             patch("core.services.run_as_scheduled_job") as schedule:
            with DjangoTestCase.captureOnCommitCallbacks(execute=True):
                start_sync(actor, "fixture", district_uuid="existing-picker-uuid", client_mutation_id="request-id")
                schedule.assert_not_called()
            schedule.assert_called_once_with("mapping.jobs.run_sync", module="mapping", job_type="mapping_locations_import",
                user=actor, params={"source_instance": "fixture", "district_id": 13}, client_mutation_id="request-id")


class CapabilityTests(TestCase):
    def test_view_permission_does_not_grant_synchronization(self):
        from mapping.access import require_capability
        user = SimpleNamespace(is_anonymous=False, has_perms=lambda rights: rights == ["view"])
        with patch.multiple(MappingConfig, enabled=True, view_perms=["view"], sync_perms=["sync"]):
            require_capability(user, "view_perms")
            with self.assertRaises(PermissionDenied):
                require_capability(user, "sync_perms")

    def test_empty_rights_are_denied(self):
        from mapping.access import require_capability
        with patch.multiple(MappingConfig, enabled=True, sync_perms=[]):
            with self.assertRaises(PermissionDenied):
                require_capability(SimpleNamespace(is_anonymous=False, has_perms=lambda rights: True), "sync_perms")
