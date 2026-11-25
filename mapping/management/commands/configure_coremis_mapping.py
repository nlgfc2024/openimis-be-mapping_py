"""Configure the read-only CoreMIS map; independent of installed importers."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from mapping.apps import DEFAULT_CONFIG


class Command(BaseCommand):
    help = 'Configure Mapping view scopes and its frontend. No source API configuration.'

    def add_arguments(self, parser):
        parser.add_argument('--district-uuid', action='append')
        parser.add_argument('--source-instance', action='append')
        parser.add_argument('--disable', action='store_true')
        parser.add_argument('--apply', action='store_true')
        overlay = parser.add_mutually_exclusive_group()
        overlay.add_argument('--enable-project-overlay', dest='project_overlay', action='store_const', const=True, default=None)
        overlay.add_argument('--disable-project-overlay', dest='project_overlay', action='store_const', const=False)

    @transaction.atomic
    def handle(self, *args, **options):
        from core.models import ModuleConfiguration
        from location.models import Location
        rows = {}
        configs = {}
        for module, layer in [('mapping','be'),('fe-mapping','fe'),('fe-location','fe'),('fe-core','fe')]:
            row = ModuleConfiguration.objects.select_for_update().filter(module=module,layer=layer).first()
            rows[(module,layer)] = row
            configs[module] = json.loads(row.config) if row else {}
        backend = {**DEFAULT_CONFIG, **configs['mapping']}
        enabled = not options['disable']
        if options['project_overlay'] is not None:
            backend['project_overlay_enabled'] = options['project_overlay']
        if options['district_uuid']:
            requested = set(options['district_uuid'])
            actual = set(map(str,Location.objects.filter(uuid__in=requested,type='R',validity_to__isnull=True).values_list('uuid',flat=True)))
            if actual != requested:
                raise CommandError('Every district UUID must identify an active CoreMIS district.')
            backend['permitted_district_uuids'] = sorted(requested)
        if options['source_instance']:
            backend['permitted_source_instances'] = options['source_instance']
        if enabled and (not backend['permitted_district_uuids'] or not backend['permitted_source_instances']):
            raise CommandError('Configure explicit --district-uuid and --source-instance scopes.')
        for key in ('sources','sync_perms','permitted_district_ids'):
            backend.pop(key,None)
        backend.update(enabled=enabled,repository='coremis')
        configs['mapping'] = backend
        configs['fe-mapping'].update(enabled=enabled,viewRights=backend['view_perms'],projectRights=backend['project_perms'],
            gpsRights=backend['gps_perms'],projectOverlayEnabled=backend['project_overlay_enabled'],menuContributionKey='openSearchReports.MainMenu')
        for key in ('sources','syncRights'):
            configs['fe-mapping'].pop(key,None)
        configs['fe-location']['useMappingDashboard'] = enabled
        for menu in configs['fe-core'].get('menus',[]):
            for entry in menu.get('submenus',[]):
                if entry.get('id') in ('mapping.dashboard','location.geospatial'):
                    entry['id'] = 'mapping.dashboard' if enabled else 'location.geospatial'
                    if 'route' in entry: entry['route'] = '/mapping/dashboard' if enabled else '/location/geospatial'
        self.stdout.write('Plan: configure read-only Mapping; credentials, importer settings and role grants unchanged.')
        if not options['apply']:
            self.stdout.write('Preview only. Add --apply to save.')
            return
        for (module,layer), row in rows.items():
            row = row or ModuleConfiguration(module=module,layer=layer,version='0.3.0',is_exposed=layer=='fe')
            row.config = json.dumps(configs[module])
            if layer == 'be': row.is_exposed = False
            row.save()
        self.stdout.write(self.style.SUCCESS('Read-only Mapping configuration saved.'))
