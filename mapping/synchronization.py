"""Reuse host jobs/staging; add ordering and configuration checks around one writer."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from mapping.apps import MappingConfig, DEFAULT_CONFIG
from mapping.configuration import source_configuration, configuration_fingerprint
from mapping.access import require_district_scope
from mapping.models import MappingSyncState


class SnapshotRejected(ValidationError):
    permanent = True


def refresh_configuration():
    from core.models import ModuleConfiguration
    from msr_etl.apps import MsrEtlConfig, DEFAULT_CONFIG as MSR_DEFAULTS
    MappingConfig.load_config(ModuleConfiguration.get_or_default("mapping", DEFAULT_CONFIG))
    MsrEtlConfig._load_config(ModuleConfiguration.get_or_default("msr_etl", MSR_DEFAULTS))


def prepare_receipt(source, unit):
    policy = getattr(source, "policy", "legacy")
    if policy not in ("mapping", "legacy"):
        raise SnapshotRejected("MAPPING_INVALID_POLICY")
    return {"version": 1, "unit_id": unit.pk, "job_uuid": str(unit.job_uuid), "policy": policy,
            "source_type": source.source_type, "source_instance": source.source_instance,
            "district_id": source.district_id,
            "fingerprint": configuration_fingerprint(source.client.config, policy)}


def current_source(receipt):
    if receipt["policy"] == "mapping":
        config = source_configuration(receipt["source_instance"])
    else:
        from msr_etl.apps import MsrEtlConfig
        config = MsrEtlConfig.get_source_config(receipt["source_type"])
    if config.get("enabled", True) is not True or config.get("source_instance") != receipt["source_instance"]:
        raise SnapshotRejected("MAPPING_SOURCE_IDENTITY_CHANGED")
    return config


def validate_snapshot(snapshot, receipt):
    if snapshot.get("source_instance") != receipt["source_instance"]:
        raise SnapshotRejected("MAPPING_SOURCE_IDENTITY_CHANGED")
    rows, memberships = snapshot.get("locations"), snapshot.get("memberships")
    if not isinstance(rows, list) or not rows or not isinstance(memberships, list):
        raise SnapshotRejected("MAPPING_INCOMPLETE_SNAPSHOT")
    if any(row.get("district_id") != receipt["district_id"] for row in rows):
        raise SnapshotRejected("MAPPING_SNAPSHOT_SCOPE_MISMATCH")
    identities = [(row.get("type"), row.get("id")) for row in rows]
    if len(set(identities)) != len(identities):
        raise SnapshotRejected("MAPPING_DUPLICATE_SOURCE_IDENTITY")
    micro_ids = {row["id"] for row in rows if row.get("type") == "catchments" and row.get("is_micro") is True}
    member_ids = [entry.get("catchment_id") for entry in memberships]
    if len(set(member_ids)) != len(member_ids) or set(member_ids) != micro_ids:
        raise SnapshotRejected("MAPPING_INCOMPLETE_MEMBERSHIPS")
    village_ids = {row["id"] for row in rows if row.get("type") == "villages"}
    assigned = set()
    for entry in memberships:
        ids = entry.get("village_ids")
        if not isinstance(ids, list) or len(set(ids)) != len(ids) or not set(ids) <= village_ids or assigned.intersection(ids):
            raise SnapshotRejected("MAPPING_MEMBERSHIP_CONFLICT")
        assigned.update(ids)


def validate_receipt(unit):
    snapshot = unit.raw_payload or {}
    receipt = snapshot.get("_mapping")
    if (not isinstance(receipt, dict) or receipt.get("version") != 1
            or receipt.get("unit_id") != unit.pk or receipt.get("job_uuid") != str(unit.job_uuid)
            or receipt.get("source_type") != unit.source_type or str(receipt.get("district_id")) != unit.unit_code
            or receipt.get("policy") not in ("mapping", "legacy")):
        raise SnapshotRejected("MAPPING_STAGE_RECEIPT_REQUIRED_RESTAGE")
    return receipt


@transaction.atomic
def apply_unit(unit, user):
    receipt = validate_receipt(unit)
    refresh_configuration()  # A worker may have outlived a configuration change.
    config = current_source(receipt)
    fingerprint = configuration_fingerprint(config, receipt["policy"])
    if not constant_time_compare(fingerprint, receipt.get("fingerprint", "")):
        raise SnapshotRejected("MAPPING_CONFIG_CHANGED_RESTAGE")
    require_district_scope(user, receipt["source_instance"], receipt["district_id"], receipt["policy"])
    validate_snapshot(unit.raw_payload, receipt)
    state, _ = MappingSyncState.objects.get_or_create(
        source_instance=receipt["source_instance"], district_msr_id=receipt["district_id"])
    state = MappingSyncState.objects.select_for_update().get(pk=state.pk)
    # Recheck after waiting for a concurrent source/district transaction.
    refresh_configuration()
    if not constant_time_compare(configuration_fingerprint(current_source(receipt), receipt["policy"]), fingerprint):
        raise SnapshotRejected("MAPPING_CONFIG_CHANGED_RESTAGE")
    require_district_scope(user, receipt["source_instance"], receipt["district_id"], receipt["policy"])
    if unit.pk < state.last_applied_unit_id:
        raise SnapshotRejected("MAPPING_STALE_SNAPSHOT_RESTAGE")
    rows = unit.raw_payload["locations"]
    if unit.pk == state.last_applied_unit_id:
        return len(rows)
    # Keep the proven location writer and its stable reference/reviewed-link IDs.
    from location.msr_reference import MsrReferenceWriter
    writer = MsrReferenceWriter(receipt["source_instance"])
    writer.push(rows)
    writer.replace_memberships(unit.raw_payload["memberships"])
    state.last_applied_unit_id = unit.pk
    state.last_successful_sync = timezone.now()
    state.save(update_fields=["last_applied_unit_id", "last_successful_sync"])
    return len(rows)
