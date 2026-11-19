from copy import deepcopy
import os
from django.core.exceptions import ValidationError
from django.utils.crypto import salted_hmac

from mapping.apps import MappingConfig
from mapping.providers.msr_v3 import MsrV3Provider


def source_configuration(source_instance):
    source = deepcopy(MappingConfig.sources.get(source_instance) or {})
    if not source or source.get("enabled", True) is not True:
        raise ValidationError("MAPPING_SOURCE_UNCONFIGURED")
    legacy_type = source.get("legacy_source_type")
    if legacy_type:
        from msr_etl.apps import MsrEtlConfig
        legacy = MsrEtlConfig.get_source_config(legacy_type)
        if legacy.get("source_instance") != source_instance or legacy.get("enabled", True) is not True:
            raise ValidationError("MAPPING_SOURCE_IDENTITY_CHANGED")
        source = {**legacy, **source}
    source["source_instance"] = source_instance
    if source.get("provider", "msr_v3") != "msr_v3":
        raise ValidationError("MAPPING_UNKNOWN_PROVIDER")
    return source


def configuration_fingerprint(config, policy):
    import json
    data = {"protocol": "mapping-msr-v3-v1", "source": deepcopy(config), "policy": policy}
    if config.get("token_env"):
        data["credential_version"] = os.environ.get(config["token_env"], "")
    if policy == "mapping":
        data["scope"] = {key: getattr(MappingConfig, key) for key in
                         ("enabled", "repository", "sync_perms", "permitted_district_ids", "permitted_source_instances")}
    # A keyed hash detects secret/config changes without persisting secret material.
    return salted_hmac("mapping.snapshot-config", json.dumps(data, sort_keys=True), algorithm="sha256").hexdigest()


def provider_for(source_instance):
    provider = MsrV3Provider(source_configuration(source_instance))
    provider.auth.get_auth_header()  # Validate credentials without network access.
    return provider
