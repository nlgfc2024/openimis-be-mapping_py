# CoreMIS Mapping backend

Mapping displays authorized geographic information already available to CoreMIS.
It has **no dependency on MSR or `msr_etl`**, owns no API credentials and starts no
source imports. It can display geography published by MSR ETL, other importers or
local CoreMIS processes through the same local geographic store.

## Responsibilities

- `location.GeographicFeature` holds source identity, local district/location or
  micro-catchment links, coordinates, publication metadata and accepted GeoJSON.
- `location.GeographicMembership` holds explicitly imported coverage relationships.
- Mapping reads these records through its repository adapter and applies its view
  capability, deployment scopes and existing CoreMIS district assignments.
- Importers retrieve/validate source publications and write accepted local data.
  MSR-specific authentication, v3/v2 requests, staging, retries and write ordering
  belong entirely to `msr_etl`.

Opening a map or clicking **Refresh map** performs local reads. It does not call
MSR, renew signed URLs or trigger synchronization. Last accepted geometry remains
available when an upstream source is offline; a failed import is reported through
refresh status. Authoritative withdrawal removes geometry; a newer accepted
publication can restore it.

## Queries

`mappingAreas` is the source-neutral paginated query. It supports `kind`,
`sourceInstance`, `districtUuid` and `microCatchmentUuid`. Kinds used by the pilot
include `district`, `traditional_authority`, `group_village_head`, `village` and
`micro_catchment`. Other publishers may supply other kinds.

`mappingGeometryAccess(referenceId: ...)` reads accepted local GeoJSON. IDs are
opaque; clients must use IDs returned by the API rather than constructing them.
The `geo:` namespace distinguishes new publication IDs from historical numeric
reference IDs, which are resolved through the legacy CoreMIS reference key.

The older `mappingReferences`, `mappingReference` and `mappingVerifiedVillages`
read operations remain as compatibility interfaces. Their MSR-named fields are
legacy provenance aliases, not live MSR queries. `mappingStartSync` and
`mappingSyncRun` are retired: source imports use the existing MSR ETL APIs/UI.

## Configuration

ModuleConfiguration: module `mapping`, layer `be`, non-exposed. Disabled by default.

```json
{
  "enabled": true,
  "repository": "coremis",
  "view_perms": ["954001"],
  "project_perms": ["954004"],
  "permitted_district_uuids": ["COREMIS_DISTRICT_UUID"],
  "permitted_source_instances": ["msr-malawi", "local-survey"],
  "max_page_size": 100
}
```

Source instance is provenance/access scope; no URL or token is configured here.
Scopes must be explicit. Source instance names do not select an upstream client.
The core role registry supplies view/project rights. Import execution continues
to use MSR ETL's existing right 953002; retired Mapping sync right 954002 does not
start imports. Role grants are not transferred or broadened automatically.

```bash
python manage.py configure_coremis_mapping --district-uuid COREMIS_DISTRICT_UUID --source-instance msr-malawi
python manage.py configure_coremis_mapping --district-uuid COREMIS_DISTRICT_UUID --source-instance msr-malawi --apply
```

## Development and verification

Install the package in editable mode using the selected nlgfc2024 assembly:

```bash
python -m pip install --no-deps --no-build-isolation -e ../openimis-be-mapping_py
python manage.py check
python manage.py migrate
```

Portable tests: `python -m mapping.tests.run_unit`. The optional CoreMIS integration
suite is `python manage.py shell -c 'from msr_etl.tests.run_geo_host import run; run()'`.
It tests the combined importer/display deployment in disposable PostgreSQL tables.
Mapping's portable suite runs without the MSR ETL package or CoreMIS adapter.

See [ownership handover](docs/MSR_IMPORT_OWNERSHIP.md) for migration, pilot evidence,
rollback requirements and remaining work. Historical chunk documents describe the
implementation at their recorded dates and may reference retired APIs.

## Geographic point layers and freshness

`mappingPoints(areaReferenceId, offset, limit)` returns paginated geographic
reference coordinates from the same authorized local store. The parent must be
a visible district or micro-catchment. District scope uses its source and local
district; micro-catchment scope includes the area itself and stored verified
memberships. Polygon containment and manually selected GVHs never determine point
membership. This feed does not query household/beneficiary programme records.

`totalCount` counts usable points; `scopedCount` counts authorized records before
coordinate validation. A micro-catchment with 66 verified villages therefore has
67 scoped records, including the micro-catchment itself. Coordinates must be a
finite latitude/longitude pair within WGS84 bounds. Explicit missing, unavailable,
invalid, withheld, removed or withdrawn point statuses are excluded. A numeric
pair with unspecified quality is labelled as such; its accuracy is not inferred.

`mappingGeometryAccess` additionally exposes `observedRevision`, `importedAt` and
`acceptedAt` from the same local record as the geometry. The frontend distinguishes
last accepted geometry from a newer imported publication or a failed replacement.
Reference metadata also exposes `geometryRevision` and `geometryUpdatedAt`.
These are CoreMIS import/acceptance times, not a claim about current upstream data.

See [point and freshness validation](docs/POINT_LAYERS_AND_FRESHNESS.md).
