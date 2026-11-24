# Geographic points and publication freshness — 23 November 2026

This chunk extends the source-neutral local Mapping reader. MSR imports continue
in MSR ETL. No source credentials, upstream requests, beneficiary GPS feeds or new
geographic records are introduced by the display implementation.

## Features and existing facilities reused

- Existing CoreMIS district picker and project micro-catchment context.
- Existing Mapping view rights, source/district scopes and CoreMIS assignments.
- Existing GeographicFeature latitude/longitude/status fields and explicit
  GeographicMembership relationships; no model migration is needed.
- CoreMIS shared date formatting and the existing Material UI themed controls,
  chips, tooltips and pagination.
- Existing bounded SVG polygon renderer, extended to project reference points,
  fit visible datasets, toggle layers and select points by mouse/keyboard.

The map supports point-only coordinate records without requiring boundary files.
Geographic coordinates are independent of polygon publication availability.
No polygon centroid is substituted for missing source coordinates. At the poles,
Mercator display clamps latitude to 85 degrees and states this limitation while
point details retain the original WGS84 coordinates.

## Scoped API

```graphql
query Points($area: ID!, $offset: Int!, $limit: Int!) {
  mappingPoints(areaReferenceId: $area, offset: $offset, limit: $limit) {
    totalCount
    scopedCount
    items { id name kind sourceInstance externalId latitude longitude pointStatus syncedAt }
  }
}
```

Area IDs must come from the authorized area query. District points are restricted
to that source and CoreMIS district. Micro-catchment points are restricted to the
selected area plus stored verified membership. Counts are computed inside those
scopes before pagination. A point inside a polygon without membership is excluded;
an explicit member outside a polygon is not silently discarded.

Latitude/longitude pairs must be finite and within [-90,90]/[-180,180]. Missing
pairs and explicitly unusable statuses are excluded. Zero coordinates remain valid
WGS84 values when their status permits display. Unknown quality is shown as
unspecified rather than promoted to a surveyed/verified coordinate.

Metadata lists and point pages defer large geometry JSON; actual geometry remains
a separate scoped read. Pagination defaults to 50, with the existing backend cap.
Only the current page is drawn and fitted. Refresh/identity/scope changes clear
stale query results and removed point details.

## Freshness semantics

- Last imported: CoreMIS geographic record import time.
- Geometry accepted: acceptance time of the displayed local geometry.
- Last imported publication revision: latest metadata accepted by the importer.
- Displayed revision: last accepted geometry revision, which may be older.

Failed replacement or a newer imported revision keeps the last accepted boundary
with an explicit warning. Authoritative withdrawal displays no boundary. The map
never equates a recent CoreMIS read with a recent source import. Optional numeric
`fe-mapping.staleAfterDays` enables an import-age warning; no threshold is assumed
when omitted. It does not schedule imports.

## Verification and pilot data

Backend tests cover scoped/hidden area IDs, permissions, pagination, verified
membership, cross-source exclusion and missing/out-of-range/non-finite/unavailable
coordinates. Frontend checks cover combined and point-only fitting, coordinate
validation, large revision comparison, explicit age thresholds, host date-format
reuse, keyboard point details, layer hiding and empty-data refresh.

The initial read-only Dedza audit found 3,560 geographic records and **zero stored
coordinate pairs**; point status was unavailable for every record. The pilot
therefore correctly shows an empty point layer until a legitimate geographic
publisher supplies coordinates and the existing import publishes them locally.
Rendering checks use isolated test fixtures, not invented pilot records.

The existing 66 verified MTANTHO memberships are independent of coordinate
availability. They remain coverage evidence even when none has a usable point.
This chunk does not establish enrolled-beneficiary GPS or surveyed accuracy.
Full browser/operator confirmation after refreshing the deployed app remains a
separate acceptance step; automated component fixtures are not that confirmation.

## Final validation — 24 November 2026

- Portable backend suite: 17 tests passed.
- Frontend module, projection, coordinate and publication tests passed.
- Host UI component fixtures passed, including point-only display, keyboard
  selection, host date formatting, layer hiding and refresh removal.
- Mapping package build and standalone JavaScript undefined-variable checks passed.
- A fresh Django system check could not connect to PostgreSQL at
  `127.0.0.1:5432` (server closed the connection). The chained migration check,
  PostgreSQL integration suite and a new live pilot audit remain pending until
  database connectivity is restored. This does not change the earlier pilot audit
  above; it must not be reported as a fresh database verification.

No database migration is introduced in this chunk. Restart the backend and reload
the frontend together because the new frontend requests additive GraphQL fields.
