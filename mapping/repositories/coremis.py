"""CoreMIS store adapter. Existing tables and the existing writer remain authoritative."""
from django.db.models import Exists, OuterRef
from mapping.apps import MappingConfig


class CoremisRepository:
    def references(self, user):
        from location.geospatial import permitted_references
        qs = permitted_references(user)
        # An enabled mapping deployment must declare its allowed district scope.
        permitted = [str(value) for value in MappingConfig.permitted_district_ids]
        if not permitted or not MappingConfig.permitted_source_instances:
            return qs.none()
        return qs.filter(district_msr_id__in=permitted, source_instance__in=MappingConfig.permitted_source_instances)

    def list_references(self, user, filters, offset, limit):
        qs = self.references(user)
        for key in ("source_instance", "msr_type", "district_msr_id", "is_micro"):
            if filters.get(key) is not None:
                qs = qs.filter(**{key: filters[key]})
        if filters.get("micro_catchment_uuid"):
            qs = qs.filter(micro_catchment__uuid=filters["micro_catchment_uuid"],
                           micro_catchment__validity_to__isnull=True)
        if filters.get("parent_reference_id"):
            parent = self.get_reference(user, filters["parent_reference_id"])
            if parent is None:
                return [], 0
            qs = qs.filter(source_instance=parent.source_instance,
                           parents__contains=[{"type": parent.msr_type, "id": parent.msr_id}])
        total = qs.count()
        rows = list(qs.select_related("micro_catchment").order_by("source_instance", "msr_type", "msr_id")[offset:offset+limit])
        return rows, total

    def get_reference(self, user, reference_id):
        return self.references(user).select_related("micro_catchment").filter(pk=reference_id).first()

    def verified_villages(self, user, catchment, offset, limit):
        from location.models import MsrCatchmentVillage
        links = MsrCatchmentVillage.objects.filter(catchment_id=catchment.pk, village_id=OuterRef("pk"))
        qs = self.references(user).filter(source_instance=catchment.source_instance, msr_type="villages")
        qs = qs.annotate(_member=Exists(links)).filter(_member=True)
        return list(qs.order_by("msr_id")[offset:offset+limit]), qs.count()

    def geometry(self, user, reference):
        from msr_etl.geometry_access import load_geometry
        return load_geometry(reference)
