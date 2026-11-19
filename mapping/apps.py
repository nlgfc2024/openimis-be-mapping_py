from copy import deepcopy
from django.apps import AppConfig
from mapping.rights import CAPABILITIES

DEFAULT_CONFIG = {
    "enabled": False,
    "repository": "none",
    **{key: [str(value)] for key, value in CAPABILITIES.items()},
    "permitted_district_ids": [],
    "permitted_source_instances": [],
    "max_page_size": 100,
    "project_overlay_enabled": False,
    "sources": {},
}


class MappingConfig(AppConfig):
    name = "mapping"
    default_auto_field = "django.db.models.BigAutoField"
    enabled = False
    repository = "none"
    view_perms = []
    sync_perms = []
    manage_perms = []
    project_perms = []
    gps_perms = []
    permitted_district_ids = []
    permitted_source_instances = []
    max_page_size = 100
    project_overlay_enabled = False
    sources = {}

    @classmethod
    def load_config(cls, config):
        for key, value in DEFAULT_CONFIG.items():
            setattr(cls, key, deepcopy(config.get(key, value)))

    def ready(self):
        # No provider construction, MSR calls, synchronization or writes at startup.
        from core.models import ModuleConfiguration
        self.load_config(ModuleConfiguration.get_or_default("mapping", DEFAULT_CONFIG))
