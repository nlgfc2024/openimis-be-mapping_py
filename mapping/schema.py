import graphene
from graphene.types.generic import GenericScalar
from django.core.exceptions import PermissionDenied, ValidationError

from mapping.apps import MappingConfig
from mapping.repositories import get_repository


def authorize(user):
    from mapping.access import require_capability
    require_capability(user, "view_perms")


def page_limits(offset, limit):
    if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= min(MappingConfig.max_page_size, 200):
        raise ValidationError("MAPPING_INVALID_PAGE")


class MappingReference(graphene.ObjectType):
    id = graphene.ID()
    source_instance = graphene.String()
    msr_type = graphene.String()
    msr_id = graphene.String()
    district_msr_id = graphene.String()
    code = graphene.String()
    name = graphene.String()
    is_micro = graphene.Boolean()
    latitude = graphene.Float()
    longitude = graphene.Float()
    point_status = graphene.String()
    geometry_relation = graphene.String()
    geometry_sha256 = graphene.String()
    geometry_source = graphene.String()
    revision = graphene.String()
    boundary_status = graphene.String()
    synced_at = graphene.DateTime()
    micro_catchment_uuid = graphene.String()
    matched = graphene.Boolean()

    def resolve_micro_catchment_uuid(self, info):
        target = getattr(self, "micro_catchment", None)
        return target.uuid if target and target.validity_to is None else None

    def resolve_matched(self, info):
        return bool(getattr(self, "location_id", None) or getattr(self, "micro_catchment_id", None))


class MappingReferencePage(graphene.ObjectType):
    items = graphene.List(MappingReference)
    total_count = graphene.Int()


class MappingGeometry(graphene.ObjectType):
    reference_id = graphene.ID()
    status = graphene.String()
    revision = graphene.String()
    relation = graphene.String()
    source = graphene.String()
    geojson = GenericScalar()


class MappingSyncRun(graphene.ObjectType):
    id = graphene.ID()
    client_mutation_id = graphene.String()
    status = graphene.String()
    total = graphene.Int()
    processed = graphene.Int()
    metrics = GenericScalar()
    error = graphene.String()
    created_at = graphene.DateTime()
    started_at = graphene.DateTime()
    finished_at = graphene.DateTime()


class Query(graphene.ObjectType):
    mapping_sync_run = graphene.Field(MappingSyncRun, job_uuid=graphene.String(), client_mutation_id=graphene.String())

    def resolve_mapping_sync_run(self, info, **kwargs):
        from mapping.jobs import visible_sync_job
        return visible_sync_job(info.context.user, **kwargs)
    mapping_references = graphene.Field(
        MappingReferencePage, source_instance=graphene.String(), msr_type=graphene.String(),
        district_msr_id=graphene.String(), micro_catchment_uuid=graphene.String(),
        parent_reference_id=graphene.ID(), is_micro=graphene.Boolean(),
        offset=graphene.Int(default_value=0), limit=graphene.Int(default_value=100),
    )
    mapping_reference = graphene.Field(MappingReference, reference_id=graphene.ID(required=True))
    mapping_verified_villages = graphene.Field(
        MappingReferencePage, catchment_reference_id=graphene.ID(required=True),
        offset=graphene.Int(default_value=0), limit=graphene.Int(default_value=100),
    )
    mapping_geometry_access = graphene.Field(MappingGeometry, reference_id=graphene.ID(required=True))

    def resolve_mapping_references(self, info, offset=0, limit=100, **filters):
        authorize(info.context.user)
        page_limits(offset, limit)
        rows, total = get_repository().list_references(info.context.user, filters, offset, limit)
        return MappingReferencePage(items=rows, total_count=total)

    def resolve_mapping_reference(self, info, reference_id):
        authorize(info.context.user)
        return visible_reference(get_repository(), info.context.user, reference_id)

    def resolve_mapping_verified_villages(self, info, catchment_reference_id, offset=0, limit=100):
        authorize(info.context.user)
        page_limits(offset, limit)
        repository = get_repository()
        catchment = visible_reference(repository, info.context.user, catchment_reference_id)
        if catchment.msr_type != "catchments" or not catchment.is_micro:
            raise ValidationError("MAPPING_INVALID_CATCHMENT")
        rows, total = repository.verified_villages(info.context.user, catchment, offset, limit)
        return MappingReferencePage(items=rows, total_count=total)

    def resolve_mapping_geometry_access(self, info, reference_id):
        authorize(info.context.user)
        repository = get_repository()
        reference = visible_reference(repository, info.context.user, reference_id)
        return MappingGeometry(reference_id=str(reference.pk), **repository.geometry(info.context.user, reference))


def visible_reference(repository, user, reference_id):
    if not isinstance(reference_id, str) or not reference_id.isdigit():
        raise ValidationError("MAPPING_INVALID_REFERENCE")
    reference = repository.get_reference(user, int(reference_id))
    if reference is None:
        raise PermissionDenied("MAPPING_REFERENCE_UNAVAILABLE")
    return reference


# Keep portable read-schema tests free of host-specific mutation imports.
def __getattr__(name):
    if name == "Mutation":
        from mapping.gql_mutations import MappingStartSyncMutation
        mutation = type("Mutation", (graphene.ObjectType,), {"mapping_start_sync": MappingStartSyncMutation.Field()})
        globals()["Mutation"] = mutation
        return mutation
    raise AttributeError(name)
