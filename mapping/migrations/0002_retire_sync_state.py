from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('mapping', '0001_source_district_sync_state')]
    operations = [migrations.SeparateDatabaseAndState(
        state_operations=[migrations.DeleteModel(name='MappingSyncState')], database_operations=[])]
