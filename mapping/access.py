from django.core.exceptions import PermissionDenied, ValidationError
from mapping.apps import MappingConfig


def require_capability(user, capability):
    rights = getattr(MappingConfig, capability)
    if (not MappingConfig.enabled or user is None or user.is_anonymous or not getattr(user, "is_active", True) or not rights
            or not all(user.has_perms([right]) for right in rights)):
        raise PermissionDenied("MAPPING_ACCESS_DENIED")
