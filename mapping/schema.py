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
    external_id = graphene.String()
    kind = graphene.String()
    district_uuid = graphene.String()
    refresh_status = graphene.String()
    geometry_revision = graphene.String()
    geometry_updated_at = graphene.DateTime()

    def resolve_district_uuid(self, info):
        district = getattr(self, "district", None)
        return district.uuid if district and district.validity_to is None else None

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

    def resolve_id(self, info):
        return public_reference_id(self)

    def resolve_district_msr_id(self, info):
        if getattr(self, 'external_type', None) == 'districts':
            return self.external_id
        return next((p['id'] for p in getattr(self, 'parent_keys', []) if p['type'] == 'districts'), None)

    def resolve_msr_id(self, info):
        return getattr(self, "external_id", None) or getattr(self, "msr_id", None)

    def resolve_msr_type(self, info):
        return getattr(self, "external_type", None) or getattr(self, "msr_type", None)

    def resolve_is_micro(self, info):
        return getattr(self, "kind", None) == "micro_catchment"

    def resolve_revision(self, info):
        return getattr(self, "observed_revision", None) if hasattr(self, "observed_revision") else getattr(self, "revision", None)

    def resolve_boundary_status(self, info):
        return getattr(self, "publication_status", None) or getattr(self, "boundary_status", None)

    def resolve_geometry_sha256(self, info):
        return getattr(self, "geometry_hash", None)

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
    refresh_status = graphene.String()
    accepted_at = graphene.DateTime()
    imported_at = graphene.DateTime()
    observed_revision = graphene.String()


class MappingPointPage(graphene.ObjectType):
    items = graphene.List(MappingReference)
    total_count = graphene.Int()
    scoped_count = graphene.Int()


class MappingHouseholdPoint(graphene.ObjectType):
    id = graphene.ID()
    code = graphene.String()
    name = graphene.String()
    kind = graphene.String()
    source_instance = graphene.String()
    latitude = graphene.Float()
    longitude = graphene.Float()
    accuracy = graphene.Float()
    elevation = graphene.Float()
    synced_at = graphene.String()
    point_status = graphene.String()


class MappingHouseholdPage(graphene.ObjectType):
    items = graphene.List(MappingHouseholdPoint)
    total_count = graphene.Int()
    scoped_count = graphene.Int()


class MappingProject(graphene.ObjectType):
    id = graphene.UUID()
    code = graphene.String()
    name = graphene.String()
    status = graphene.String()


class MappingProjectPage(graphene.ObjectType):
    items = graphene.List(MappingProject)
    total_count = graphene.Int()


class Query(graphene.ObjectType):
    mapping_catchment_projects = graphene.Field(MappingProjectPage, reference_id=graphene.ID(required=True),
        offset=graphene.Int(default_value=0), limit=graphene.Int(default_value=50))

    def resolve_mapping_catchment_projects(self, info, reference_id, offset=0, limit=50):
        from mapping.access import require_capability
        authorize(info.context.user)
        require_capability(info.context.user, 'project_perms')
        page_limits(offset, limit)
        repository = get_repository()
        reference = visible_reference(repository, info.context.user, reference_id)
        if reference.kind != 'micro_catchment':
            raise ValidationError('MAPPING_INVALID_CATCHMENT')
        rows, total = repository.catchment_projects(info.context.user, reference, offset, limit)
        return MappingProjectPage(items=rows, total_count=total)

    mapping_project_households = graphene.Field(MappingHouseholdPage, project_id=graphene.UUID(required=True),
        offset=graphene.Int(default_value=0), limit=graphene.Int(default_value=50))

    def resolve_mapping_project_households(self, info, project_id, offset=0, limit=50):
        from mapping.access import require_capability
        authorize(info.context.user)
        require_capability(info.context.user, 'project_perms')
        require_capability(info.context.user, 'gps_perms')
        if not MappingConfig.project_overlay_enabled:
            raise PermissionDenied('MAPPING_PROJECT_OVERLAY_DISABLED')
        page_limits(offset, limit)
        rows, total, scoped = get_repository().project_households(info.context.user, project_id, offset, limit)
        return MappingHouseholdPage(items=rows, total_count=total, scoped_count=scoped)

    mapping_points = graphene.Field(MappingPointPage, area_reference_id=graphene.ID(required=True),
        offset=graphene.Int(default_value=0), limit=graphene.Int(default_value=50))

    def resolve_mapping_points(self, info, area_reference_id, offset=0, limit=50):
        authorize(info.context.user)
        page_limits(offset, limit)
        repository = get_repository()
        area = visible_reference(repository, info.context.user, area_reference_id)
        if area.kind not in ('district', 'micro_catchment'):
            raise ValidationError('MAPPING_INVALID_POINT_SCOPE')
        rows, total, scoped = repository.points(info.context.user, area, offset, limit)
        return MappingPointPage(items=rows, total_count=total, scoped_count=scoped)

    mapping_areas = graphene.Field(MappingReferencePage, kind=graphene.String(), source_instance=graphene.String(),
        district_uuid=graphene.String(), micro_catchment_uuid=graphene.String(), offset=graphene.Int(default_value=0), limit=graphene.Int(default_value=100))

    def resolve_mapping_areas(self, info, offset=0, limit=100, **filters):
        return Query.resolve_mapping_references(self, info, offset=offset, limit=limit, **filters)

    mapping_references = graphene.Field(
        MappingReferencePage, source_instance=graphene.String(), msr_type=graphene.String(),
        district_msr_id=graphene.String(), micro_catchment_uuid=graphene.String(),
        district_uuid=graphene.String(),
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
        if getattr(catchment, "kind", None) != "micro_catchment" and not (getattr(catchment, "msr_type", None) == "catchments" and getattr(catchment, "is_micro", False)):
            raise ValidationError("MAPPING_INVALID_CATCHMENT")
        rows, total = repository.verified_villages(info.context.user, catchment, offset, limit)
        return MappingReferencePage(items=rows, total_count=total)

    def resolve_mapping_geometry_access(self, info, reference_id):
        authorize(info.context.user)
        repository = get_repository()
        reference = visible_reference(repository, info.context.user, reference_id)
        return MappingGeometry(reference_id=public_reference_id(reference), **repository.geometry(info.context.user, reference))


def visible_reference(repository, user, reference_id):
    if not isinstance(reference_id, str) or not (reference_id.isdigit() or (reference_id.startswith('geo:') and reference_id[4:].isdigit())):
        raise ValidationError("MAPPING_INVALID_REFERENCE")
    reference = repository.get_reference(user, reference_id if reference_id.startswith('geo:') else int(reference_id))
    if reference is None:
        raise PermissionDenied("MAPPING_REFERENCE_UNAVAILABLE")
    return reference


def public_reference_id(reference):
    if getattr(reference, 'external_type', None) is not None:
        return 'geo:' + str(reference.pk)
    return str(getattr(reference, 'id', None) or reference.pk)
