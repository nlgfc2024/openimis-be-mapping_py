"""Scheduling and progress are owned by core; staging/recovery stay in MSR ETL."""
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError

from mapping.access import require_district_scope, resolve_district
from mapping.configuration import provider_for
from mapping.providers.district import DistrictSource
from mapping.synchronization import refresh_configuration


def start_sync(user, source_instance, district_id=None, district_uuid=None, client_mutation_id=None):
    refresh_configuration()
    district_id = resolve_district(user, source_instance, district_id, district_uuid)
    require_district_scope(user, source_instance, district_id)
    provider_for(source_instance)  # Validate config and secret reference; never HTTP here.
    from core.services import run_as_scheduled_job
    # Reuse the host's async mutation correlation/progress polling convention.
    transaction.on_commit(lambda: run_as_scheduled_job(
        "mapping.jobs.run_sync", module="mapping", job_type="mapping_locations_import", user=user,
        params={"source_instance": source_instance, "district_id": district_id},
        client_mutation_id=client_mutation_id,
    ))


def run_sync(reporter, source_instance, district_id):
    refresh_configuration()
    user = reporter.job.user
    require_district_scope(user, source_instance, district_id)
    provider = provider_for(source_instance)
    source = DistrictSource(provider, source_instance, district_id)
    from msr_etl.jobs import _run_staged_import
    from msr_etl.models import MsrEtlSyncUnit
    _run_staged_import(reporter, source, MsrEtlSyncUnit.Kind.LOCATION)


def visible_sync_job(user, job_uuid=None, client_mutation_id=None):
    from core.models import AsyncJob
    from mapping.access import require_capability
    from mapping.apps import MappingConfig
    require_capability(user, "sync_perms")
    if bool(job_uuid) == bool(client_mutation_id):
        raise ValidationError("MAPPING_JOB_IDENTIFIER_REQUIRED")
    qs = AsyncJob.objects.filter(module="mapping", job_type="mapping_locations_import")
    if job_uuid:
        import uuid
        try:
            qs = qs.filter(pk=uuid.UUID(str(job_uuid)))
        except ValueError:
            raise ValidationError("MAPPING_INVALID_JOB_ID") from None
    else:
        qs = qs.filter(client_mutation_id=client_mutation_id)
    # Do not reveal another operator's jobs unless separately authorized to manage.
    can_manage = bool(MappingConfig.manage_perms) and all(user.has_perms([p]) for p in MappingConfig.manage_perms)
    if not can_manage:
        qs = qs.filter(user=user)
    job = qs.order_by("-created_at").first()
    if job is None:
        return None
    params = job.params or {}
    require_district_scope(user, params.get("source_instance"), params.get("district_id"))
    return job
