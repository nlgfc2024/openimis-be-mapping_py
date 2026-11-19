# openIMIS / CoreMIS Mapping backend

Dedicated Django application `mapping`, package `openimis-be-mapping`.

## Current delivery

The module supplies permission-scoped read APIs and MSR synchronization. It reuses
core jobs, async mutations, progress and permission discovery; MSR ETL staging and
recovery; and the existing location reference/membership writer. It adds one
source/district coordination table, not a second geographic store.

The new module remains disabled by default. The current pilot route and project
component continue until the frontend bridge chunk. Streaming, programme/GPS
overlays and complete lifecycle acceptance remain pending.

Read APIs: `mappingReferences`, `mappingReference`, `mappingVerifiedVillages`,
`mappingGeometryAccess`. Geometry returns bounded validated GeoJSON through the
existing authenticated backend delivery service.
Synchronization APIs: `mappingStartSync`, `mappingSyncRun`.

## Local assembly setup

Use the existing nlgfc2024 assembly's pinned dependencies and editable packages:

```json
{"name":"mapping","pip":"-e ../openimis-be-mapping_py"}
```

```bash
python -m pip install --no-deps --no-build-isolation -e ../openimis-be-mapping_py
python manage.py check
python manage.py makemigrations mapping --check --dry-run
python manage.py migrate mapping
```

Django commands run from the assembly's manage.py directory. Module startup reads
configuration; it does not construct a provider, call MSR or synchronize records.
`mapping.urls` follows the core module URL registration convention.

## Configuration and rights

Backend ModuleConfiguration uses module `mapping`, layer `be`, **non-exposed**.
The core registry discovers the following capabilities; assign rights through the
existing Roles Management feature. No roles are granted automatically.

| Capability | Right |
| --- | --- |
| View mapping | 954001 |
| Synchronize | 954002 |
| Manage mapping / review other operators' jobs | 954003 |
| Project overlays, reserved for subsequent work | 954004 |
| Beneficiary GPS, reserved for subsequent work | 954005 |

These IDs were checked against the current nlgfc2024 catalogue and stored
RoleRight values before allocation. Other host profiles must check their own
catalogues. Allocating rights does not implement or expose the pending overlays.

Controlled activation example, after migration and role assignment:

```json
{
  "enabled": true,
  "repository": "coremis",
  "view_perms": ["954001"],
  "sync_perms": ["954002"],
  "manage_perms": ["954003"],
  "project_perms": ["954004"],
  "gps_perms": ["954005"],
  "permitted_district_ids": [13],
  "permitted_source_instances": ["msr-malawi"],
  "sources": {
    "msr-malawi": {"provider": "msr_v3", "enabled": true, "legacy_source_type": "msr_geo_v3"}
  },
  "max_page_size": 100,
  "project_overlay_enabled": false
}
```

The legacy source alias reuses existing backend-held credentials without copying
them. Independent sources may supply `base_url`, `token_env` (the server environment
variable name), timeouts and pagination limits instead. Remote MSR addresses
require HTTPS; HTTP is permitted for localhost, including the pilot on port 8080.
No credentials or temporary download URLs are stored in snapshot receipts.

Scope reuses CoreMIS district assignments and location permissions. Empty scopes
permit no districts; empty permission arrays deny access. Workers reload source
configuration and host permissions before writing and after acquiring the lock.

## Tests

Portable read/provider tests, from this package directory:

```bash
python -m mapping.tests.run_unit
```

CoreMIS host regression tests, from the assembly's manage.py directory:

```bash
python manage.py shell -c 'from mapping.tests.run_host import run; run()'
```

The host runner requires PostgreSQL CREATE SCHEMA permission. It writes only to a
disposable schema, then removes it. It covers ordering, real concurrent workers,
rollback, configuration changes, revoked scope, scheduling and legacy imports.

## Compatibility boundary

The repository and synchronization bridges import CoreMIS-specific models and
legacy services lazily. Disabled startup does not require their construction.
Only the selected nlgfc2024 CoreMIS host is the current compatibility target;
standalone upstream openIMIS storage and a second host profile are not certified.

Existing location reference/membership tables and reviewed MicroCatchment links
remain authoritative. Both synchronization entry points share the same writer.
Old staged geographic units without a coordination receipt require restaging.
A village belongs to one catchment; no polygon-based membership is inferred.

See [baseline](docs/BASELINE.md), [delivery chunks](docs/IMPLEMENTATION.md) and
[synchronization API](docs/SYNCHRONIZATION.md).
