# openIMIS / CoreMIS Mapping backend

Dedicated Django application `mapping`, package `openimis-be-mapping`.

## Current chunk

The package supplies a disabled-by-default, permission-scoped read API over the
existing CoreMIS reference store. No new reference/membership tables or alternate
writer are introduced. Provider transport, geometry delivery and synchronization
continue to use the proven CoreMIS MSR ETL implementation through the bridge.
This is an extraction foundation, not completion of the full mapping specification.

Queries: `mappingReferences`, `mappingReference`, `mappingVerifiedVillages` and
`mappingGeometryAccess`. The latter currently returns bounded validated GeoJSON
through GraphQL, reusing the existing authenticated backend delivery service.
An authenticated streaming endpoint is not implemented in this chunk.

## Assembly registration

Use the target assembly's pinned dependencies and conventions. For local development:

```json
{"name":"mapping","pip":"-e ../openimis-be-mapping_py"}
```

```bash
python -m pip install --no-deps --no-build-isolation -e ../openimis-be-mapping_py
python manage.py check
python manage.py makemigrations mapping --check --dry-run
python manage.py test mapping.tests
```

Run Django commands from the host assembly's manage.py directory. `mapping.urls`
is registered through the host's module URL convention and has no routes yet.
App startup reads configuration only; it does not construct a provider, call MSR,
start a sync or write geographic records.

## Configuration

Backend ModuleConfiguration: module `mapping`, layer `be`, non-exposed. Defaults:
disabled, no allocated capability rights, no permitted districts and no repository.
An enabled source must not be assumed merely because the package is installed.

```json
{
  "enabled": true,
  "repository": "coremis",
  "view_perms": ["ALLOCATED_MAPPING_VIEW_RIGHT"],
  "permitted_district_ids": [13],
  "permitted_source_instances": ["msr-malawi"],
  "max_page_size": 100,
  "project_overlay_enabled": false
}
```

Replace the placeholder through the host rights registry; do not grant blanket
access or invent a permission number. The adapter also applies the existing
CoreMIS location permissions/district assignments. An empty district scope returns
no rows. No `*` scope is assumed. Permission allocation and feature activation are
the next rollout gate; the existing pilot route remains available meanwhile.

The current bridge reads MSR credentials from the existing non-exposed MSR ETL
source configuration. Credentials are not copied into this repository or sent to
the browser. A generic provider configuration and deployment secret references
will be extracted in the next backend chunk.

## Compatibility boundary

`mapping/repositories/coremis.py` is the only adapter importing CoreMIS-specific
reference types and legacy services. These imports are lazy: disabled/unconfigured
mapping can boot without that adapter's custom models. Only the current CoreMIS
host has been integration-tested; a standalone openIMIS store and second host
validation remain pending. Do not select `coremis` on an upstream host lacking
the custom reference models.

The CoreMIS `MsrLocationReference` / `MsrCatchmentVillage` tables and reviewed
MicroCatchment links remain authoritative. Old `msrGeo*` queries and the current
MSR ETL writer remain available. New mapping sync mutations are deliberately not
exposed until district write ordering, recovery and separate rights are complete.

See [baseline](docs/BASELINE.md) and [delivery chunks](docs/IMPLEMENTATION.md).
