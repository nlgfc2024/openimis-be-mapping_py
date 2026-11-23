"""Read-only adapter for CoreMIS geography. No upstream API or importer imports."""
from django.db.models import Exists, OuterRef
from mapping.apps import MappingConfig


class CoremisRepository:
    def references(self, user):
        from location.models import GeographicFeature, allowed_micro_catchment_district_ids
        qs = GeographicFeature.objects.filter(district__uuid__in=MappingConfig.permitted_district_uuids,
            district__validity_to__isnull=True, source_instance__in=MappingConfig.permitted_source_instances)
        allowed = allowed_micro_catchment_district_ids(user)
        if allowed is not None:
            qs = qs.filter(district_id__in=allowed)
        return qs

    def list_references(self, user, filters, offset, limit):
        qs = self.references(user)
        for key in ('source_instance', 'kind'):
            if filters.get(key) is not None:
                qs = qs.filter(**{key: filters[key]})
        if filters.get('msr_type') is not None:
            qs = qs.filter(external_type=filters['msr_type'])  # Deprecated read alias.
        if filters.get('is_micro') is True:
            qs = qs.filter(kind='micro_catchment')
        elif filters.get('is_micro') is False:
            qs = qs.exclude(kind='micro_catchment')
        if filters.get('micro_catchment_uuid'):
            qs = qs.filter(micro_catchment__uuid=filters['micro_catchment_uuid'], micro_catchment__validity_to__isnull=True)
        if filters.get('district_uuid'):
            qs = qs.filter(district__uuid=filters['district_uuid'])
        if filters.get('district_msr_id'):
            districts = self.references(user).filter(kind='district', external_id=str(filters['district_msr_id']),
                source_instance=OuterRef('source_instance'), district_id=OuterRef('district_id'))
            qs = qs.annotate(_district=Exists(districts)).filter(_district=True)
        if filters.get('parent_reference_id'):
            parent = self.get_reference(user, filters['parent_reference_id'])
            if parent is None:
                return [], 0
            qs = qs.filter(source_instance=parent.source_instance,
                parent_keys__contains=[{'type': parent.external_type, 'id': parent.external_id}])
        total = qs.count()
        return list(qs.select_related('micro_catchment','district').order_by('source_instance','kind','external_id')[offset:offset+limit]), total

    def get_reference(self, user, reference_id):
        qs = self.references(user).select_related('micro_catchment','district')
        if str(reference_id).startswith('geo:'):
            return qs.filter(pk=int(str(reference_id)[4:])).first()
        # Historical numeric IDs identify the old CoreMIS reference store.
        # Never reinterpret them as a different new publication row.
        from location.geography import legacy_reference_key
        key = legacy_reference_key(reference_id)
        return qs.filter(**key).first() if key else None

    def verified_villages(self, user, catchment, offset, limit):
        from location.models import GeographicMembership
        links = GeographicMembership.objects.filter(parent=catchment, child_id=OuterRef('pk'))
        qs = self.references(user).filter(source_instance=catchment.source_instance,kind='village').annotate(_member=Exists(links)).filter(_member=True)
        return list(qs.order_by('external_id')[offset:offset+limit]), qs.count()

    def geometry(self, user, reference):
        from location.geography import local_geometry
        return local_geometry(reference)
