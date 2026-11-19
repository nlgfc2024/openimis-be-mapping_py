"""Configure the existing host registry, source alias and dashboard menu together."""
from copy import deepcopy
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from mapping.apps import DEFAULT_CONFIG


def dashboard_menu(config, enabled):
    config = deepcopy(config)
    old, new = ("location.geospatial", "mapping.dashboard") if enabled else ("mapping.dashboard", "location.geospatial")
    for menu in config.get("menus", []):
        for entry in menu.get("submenus", []):
            if entry.get("id") == old:
                entry["id"] = new
                if "route" in entry:
                    entry["route"] = "/mapping/dashboard" if enabled else "/location/geospatial"
    return config


class Command(BaseCommand):
    help = "Preview or apply the local CoreMIS mapping bridge configuration; never grants roles or copies credentials."

    def add_arguments(self, parser):
        parser.add_argument("--source-instance")
        parser.add_argument("--district-id", type=int, action="append")
        parser.add_argument("--legacy-source-type", default="msr_geo_v3")
        parser.add_argument("--disable", action="store_true")
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        from core.models import ModuleConfiguration, User
        from django.core.cache import cache
        from location.models import MsrLocationReference
        from msr_etl.apps import MsrEtlConfig
        from mapping.providers.msr_v3 import MsrV3Provider

        enabled = not options["disable"]
        rows = {}
        def read(module, layer, defaults=None):
            row = ModuleConfiguration.objects.select_for_update().filter(module=module, layer=layer).first()
            rows[(module, layer)] = row
            return {**deepcopy(defaults or {}), **(json.loads(row.config) if row else {})}

        backend = read("mapping", "be", DEFAULT_CONFIG)
        frontend = read("fe-mapping", "fe")
        location = read("fe-location", "fe")
        core = read("fe-core", "fe")
        if enabled:
            instance, districts = options["source_instance"], options["district_id"] or []
            if not instance or not districts or any(value <= 0 for value in districts):
                raise CommandError("Supply --source-instance and one or more positive --district-id values.")
            source = MsrEtlConfig.get_source_config(options["legacy_source_type"])
            if source.get("enabled") is not True or source.get("source_instance") != instance:
                raise CommandError("The existing backend MSR source must be enabled and match source_instance.")
            # Validate the backend credential without fetching or printing it.
            try:
                MsrV3Provider(source).auth.get_auth_header()
            except Exception:
                raise CommandError("The backend MSR source URL or credential is invalid.") from None
            matched = set(MsrLocationReference.objects.filter(source_instance=instance, msr_type="districts",
                msr_id__in=districts, location__type="R", location__validity_to__isnull=True).values_list("msr_id", flat=True))
            if matched != set(districts):
                raise CommandError("Every selected district needs an active reviewed CoreMIS district link.")
            backend.update(repository="coremis", permitted_source_instances=[instance], permitted_district_ids=sorted(set(districts)))
            backend["sources"] = {**backend.get("sources", {}), instance: {
                "enabled": True, "provider": "msr_v3", "legacy_source_type": options["legacy_source_type"]}}
            for key in ("view_perms", "sync_perms", "manage_perms", "project_perms", "gps_perms"):
                if not backend[key]:
                    raise CommandError("Configure nonempty mapping capabilities before activation: " + key)
            frontend.update(viewRights=backend["view_perms"], syncRights=backend["sync_perms"], projectRights=backend["project_perms"],
                menuContributionKey="openSearchReports.MainMenu", sources=[{"id": instance, "label": source.get("source_name") or instance}])
        backend["enabled"] = enabled
        frontend["enabled"] = enabled
        location["useMappingDashboard"] = enabled
        core = dashboard_menu(core, enabled)
        self.stdout.write("Plan: " + ("enable" if enabled else "disable") + " the mapping backend, frontend bridge and Dashboards entry.")
        self.stdout.write("Existing role grants and backend MSR credentials are preserved.")
        if not options["apply"]:
            self.stdout.write("Preview only. Add --apply to save.")
            return
        for module, layer, config in (("mapping", "be", backend), ("fe-mapping", "fe", frontend),
                                      ("fe-location", "fe", location), ("fe-core", "fe", core)):
            row = rows[(module, layer)] or ModuleConfiguration(module=module, layer=layer, version="0.2.0", is_exposed=layer == "fe")
            row.config = json.dumps(config)
            row.is_disabled_until = None
            if layer == "be":
                row.is_exposed = False
            row.save()
        keys = ["rights_" + str(value) for value in User.objects.filter(i_user__isnull=False).values_list("i_user_id", flat=True)]
        transaction.on_commit(lambda: cache.delete_many(keys))
        self.stdout.write(self.style.SUCCESS("Configuration saved. Restart backend/workers and reload the frontend session."))
