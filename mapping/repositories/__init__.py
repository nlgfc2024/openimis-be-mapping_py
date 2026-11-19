from django.core.exceptions import ValidationError
from mapping.apps import MappingConfig


def get_repository():
    if MappingConfig.repository == "coremis":
        # Optional host imports only occur after the configured capability is used.
        from mapping.repositories.coremis import CoremisRepository
        return CoremisRepository()
    raise ValidationError("MAPPING_REPOSITORY_UNCONFIGURED")
