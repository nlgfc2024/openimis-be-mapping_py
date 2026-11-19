# Mapping module delivery chunks

Specification inputs: CoreMIS Mapping Module Development Specification (6-page
PDF) and CoreMIS/openIMIS Mapping Module Implementation Guide supplied by the
project owner. Treat their package/API/acceptance definitions as the target.

## Chunk 1: baseline and repository boundary

Captured pilot commits in existing repositories. Created independent backend and
frontend packages on `feature/geospatial-dashboard`. Public visibility and the
one-catchment-per-village rule were confirmed by the project owner on 19 November
2026. Existing source manifests and payroll/project local links are preserved.

## Chunk 2: safe registration and read extraction

Implemented `MappingConfig`, module schema/URL registration, an optional CoreMIS
repository adapter and four mapping-specific read operations. No data migration
is needed for this adapter. Extracted the current boundary map into the new npm
package, publishing `MappingModule` and `mapping.MappingMap`, with configurable
host menu contribution and fail-closed frontend rights.

Source registration alone does not activate the new menu or change the existing
project tab. Activation requires separately allocated host capabilities and
appropriate module configuration. Existing routes continue to function.

## Chunk 3: provider and synchronization extraction

Implemented the independent MSR provider and district collector. The legacy MSR
source delegates to these components. Both entry points reuse staging/recovery
and one location writer. A keyed configuration receipt is captured before
network access and stored in the existing staging payload. The source/district
state row serializes writes and rejects older staging sequences.

Added `mappingStartSync` / `mappingSyncRun`, reusing core async mutation tracking,
scheduling after commit and progress reporting. The mutation accepts the UUID
returned by the published location district picker. View, sync, management,
project and GPS capabilities are independently discovered by the core registry;
no roles are granted automatically. The migration adds coordination state only.

Tests cover provider pagination/failures, rollback, stale ordering, configuration
changes, revoked scope, concurrent PostgreSQL workers and legacy source/staging.
UI cutover, synchronization controls and programme overlays remain subsequent
chunks. See [synchronization contract](SYNCHRONIZATION.md).

## Chunk 4: production map and CoreMIS bridge

Complete independent point handling, hierarchy choices, freshness indicators and
an authenticated geometry streaming contract where supported. Select a mapping
library compatible with the pinned hosts before adding a basemap. The extracted
pilot currently uses the existing bounded SVG polygon overlay without a basemap.
Switch the project tab and old location contribution to the published mapping
component after the new API is enabled and authorized; retain legacy URL aliases.
Add scoped project overlays and explicit link review audit workflows.

## Chunk 5: programme/GPS overlays

Identify existing MSR/CoreMIS household and beneficiary coordinate fields, their
record links, quality and provenance. No GPS field is guessed. Implement separately
permissioned feeds and documented distinct counting units. Household locations
must not be described as individual GPS observations.

## Chunk 6: acceptance and release

Repeat Dedza/MTANTHO with verified source memberships, repeat sync, later-page
failure, rollback, stale concurrent jobs, expiry, replacement, withdrawal,
restoration, point-only data, unauthorized direct IDs/counts and scope revocation.
Validate disabled startup and the boundary-only map in the selected nlgfc2024
assemblies first. Record package commits, contract fixtures, limits, timings and
rollback evidence. A separately pinned upstream openIMIS assembly can be added
later; compatibility with it is not part of the current acceptance claim.
A successful boundary pilot does not establish completed village coverage.

## Confirmed host targets

On 19 November 2026 the project owner selected the available nlgfc2024 assemblies
for the current compatibility checks:

| Host | Branch | Integration commit |
| --- | --- | --- |
| `nlgfc2024/openimis-be_py` | `feature/geospatial-dashboard` | `6bea78cc1e84c8a354e63671b8400369bbaf10f2` |
| `nlgfc2024/openimis-fe_js` | `feature/geospatial-dashboard` | `dbba83c0ebea9f128372ef0c491c67b4d4589d73` |

These local checkouts also retain the pre-existing deployment overrides recorded
by manifest checksums in BASELINE.md. Runtime baseline: Django 4.2, Graphene 2 and
React 17. The two assembly repositories form the current CoreMIS host profile;
they are not evidence of two independently validated host profiles. No upstream
openIMIS release or commit has been selected or certified by this decision.
