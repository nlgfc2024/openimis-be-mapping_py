"""Only write coordination lives here; core owns jobs and MSR ETL owns staging."""
from django.db import models


class MappingSyncState(models.Model):
    source_instance = models.CharField(max_length=100)
    district_msr_id = models.PositiveBigIntegerField()
    last_applied_unit_id = models.PositiveBigIntegerField(default=0)
    last_successful_sync = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "mapping_sync_state"
        constraints = [models.UniqueConstraint(fields=["source_instance", "district_msr_id"],
                                              name="mapping_source_district_unique")]
