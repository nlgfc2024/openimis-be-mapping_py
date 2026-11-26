"""Optional CoreMIS programme adapter; reads local enrolments and household GPS."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef, Q, F
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from mapping.apps import MappingConfig


def host_permission(user, rights):
    if not rights or not all(user.has_perms([right]) for right in rights):
        raise PermissionDenied('MAPPING_ACCESS_DENIED')


def visible_project(user, project_id):
    from django.apps import apps
    if not apps.is_installed('project_social_protection'):
        raise ValidationError('MAPPING_PROJECT_ADAPTER_UNAVAILABLE')
    from project_social_protection.models import Project
    from project_social_protection.apps import ProjectSocialProtectionConfig
    from location.models import allowed_micro_catchment_district_ids
    host_permission(user, ProjectSocialProtectionConfig.gql_project_search_perms)
    project = Project.objects.filter(pk=project_id, is_deleted=False, benefit_plan__is_deleted=False).select_related('location').first()
    location = project.location if project else None
    district = None
    while location is not None:
        if location.validity_to is not None:
            break
        if location.type == 'R':
            district = location
            break
        location = location.parent
    allowed = allowed_micro_catchment_district_ids(user)
    if (district is None or str(district.uuid) not in MappingConfig.permitted_district_uuids
            or (allowed is not None and district.pk not in allowed)):
        raise PermissionDenied('MAPPING_PROJECT_UNAVAILABLE')
    return project, district


def catchment_projects(user, reference, offset, limit):
    from django.apps import apps
    if not apps.is_installed('project_social_protection'):
        raise ValidationError('MAPPING_PROJECT_ADAPTER_UNAVAILABLE')
    from project_social_protection.apps import ProjectSocialProtectionConfig
    from project_social_protection.models import Project
    from location.models import extend_allowed_locations
    host_permission(user, ProjectSocialProtectionConfig.gql_project_search_perms)
    if (not reference.micro_catchment_id or reference.micro_catchment.validity_to is not None
            or reference.micro_catchment.district_id != reference.district_id):
        return [], 0
    # A verified source identity and explicit CoreMIS match select the projects;
    # polygon containment is never used to create or infer that relationship.
    qs = Project.objects.filter(is_deleted=False, benefit_plan__is_deleted=False,
        micro_catchment_id=reference.micro_catchment_id,
        location_id__in=extend_allowed_locations([reference.district_id]),
        location__validity_to__isnull=True)
    total = qs.count()
    return list(qs.order_by('name','pk').values('id','code','name','status')[offset:offset+limit]), total


def household_page(user, project_id, offset, limit):
    project, district = visible_project(user, project_id)
    from individual.apps import IndividualConfig
    from individual.data_source import data_source_expression
    from individual.models import Group, GroupIndividual
    from social_protection.apps import SocialProtectionConfig
    from social_protection.models import Beneficiary, GroupBeneficiary
    from project_social_protection.models import BeneficiaryProjectEnrollment, GroupBeneficiaryProjectEnrollment
    host_permission(user, IndividualConfig.gql_group_search_perms)
    host_permission(user, SocialProtectionConfig.gql_beneficiary_search_perms)

    active_groups = GroupBeneficiary.get_queryset(GroupBeneficiary.objects.filter(
        is_deleted=False, status='ACTIVE', benefit_plan_id=project.benefit_plan_id), user)
    group_links = GroupBeneficiaryProjectEnrollment.objects.filter(project=project,is_deleted=False,
        group_beneficiary__in=active_groups, group_beneficiary__group_id=OuterRef('pk'))

    active_individuals = Beneficiary.get_queryset(Beneficiary.objects.filter(
        is_deleted=False, status='ACTIVE', benefit_plan_id=project.benefit_plan_id, individual__is_deleted=False), user)
    enrolled_people = BeneficiaryProjectEnrollment.objects.filter(project=project,is_deleted=False,
        beneficiary__in=active_individuals).values('beneficiary__individual_id')
    members = GroupIndividual.objects.filter(group_id=OuterRef('pk'), is_deleted=False,
        individual_id__in=enrolled_people, individual__is_deleted=False)
    groups = Group.get_queryset(Group.objects.filter(is_deleted=False), user).annotate(
        _group_enrolled=Exists(group_links), _member_enrolled=Exists(members)).filter(
            Q(_group_enrolled=True) | Q(_member_enrolled=True))
    # Project access does not make unrelated household locations visible. Reuse
    # host row security above, and the configured district scope for each record.
    from location.models import extend_allowed_locations
    district_locations = extend_allowed_locations([district.pk])
    groups = groups.filter(location_id__in=district_locations,
                           location__validity_to__isnull=True)
    scoped = groups.count()
    usable = groups.annotate(_source=data_source_expression(),
        _gps_source=KeyTextTransform('source_type',KeyTransform('household_gps','json_ext'))).filter(
        json_ext__household_gps__coordinate_type='household',
        _gps_source=F('_source'),
        json_ext__household_gps__latitude__gte=-90, json_ext__household_gps__latitude__lte=90,
        json_ext__household_gps__longitude__gte=-180, json_ext__household_gps__longitude__lte=180)
    total = usable.count()
    rows = []
    # Select GPS metadata only: no names, identities, household members or full JSON.
    for pk, code, gps in usable.order_by('code','pk').values_list('pk','code','json_ext__household_gps')[offset:offset+limit]:
        rows.append({'id':'household:'+str(pk), 'code':code, 'name':'Household '+code,
            'kind':'household', 'source_instance':gps['source_type'],
            'latitude':gps['latitude'], 'longitude':gps['longitude'],
            'accuracy':gps.get('accuracy'), 'elevation':gps.get('elevation'),
            'synced_at':gps.get('imported_at'), 'point_status':'imported household GPS'})
    return rows, total, scoped
