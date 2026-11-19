# Chunk 4a validation — 19 November 2026

Scope: frontend synchronization controls, reuse of CoreMIS location filtering,
legacy location/project bridges and controlled pilot configuration. This is part
of Chunk 4; it does not complete point layers, streaming or programme/GPS feeds.

| Check | Result |
| --- | --- |
| Backend portable schema/provider suite | 19 passed |
| Isolated PostgreSQL host suite | 86 passed |
| New district UUID filter | Correlates source and MSR district; equal IDs in another source do not match |
| Frontend module and geometry tests | Passed |
| React 17/jsdom host component checks | Passed: disabled/view-only access, picker UUID submission, duplicate guard, core progress, project capability and legacy fallback |
| Mapping/location/project package builds | Passed; existing external dependency warnings remain in location/project |
| CoreMIS full frontend assembly build | Compiled successfully with ESLint plugin disabled, matching the existing host build setup |
| Local project resolution regression | Passed; project/payroll local links preserved |
| Configuration preview | Validated existing MSR credential alias and reviewed district link; no HTTP fetch |
| Pilot configuration apply | Backend and frontend enabled for msr-malawi / district 13; no role grants changed |
| Existing Dashboards allowlist | location.geospatial replaced by mapping.dashboard; other entries preserved |
| Activated composed API read | Dedza selected through CoreMIS UUID; matched MTANTHO reference returned |
| Existing reference integrity | Reference count and reviewed MTANTHO link unchanged |

Public route: `/front/mapping/dashboard`. Legacy `/front/location/geospatial`
delegates to the shared component when enabled and keeps its existing location
route permission. The project Boundary map tab passes the project's existing
micro-catchment UUID and requires mapping view/project capabilities.

The local configuration was applied using:

```bash
python manage.py configure_coremis_mapping --source-instance msr-malawi --district-id 13 --apply
```

Backend source configuration is non-exposed and aliases existing MSR ETL
credentials. Frontend source options contain only safe identifiers and labels.
Restart backend/workers and reload the frontend session. Existing administrators
receive registry rights through the normal host mechanism; ordinary users need
explicit mapping rights assigned through Roles Management.

Rollback to legacy frontend:

```bash
python manage.py configure_coremis_mapping --disable --apply
```

The coordination table and geographic records remain in place for the existing
legacy synchronization path. No reference, project or payroll deletion is needed.

The UI tests exercise published-component contracts using host React/jsdom; they
are not a full authenticated browser session. A live end-to-end synchronization
started from the new UI remains a pilot acceptance step. Existing MSR-verified
MTANTHO coverage was empty; manually configured CoreMIS GVHs do not establish
verified village coverage. Basemap, point-only rendering, programme/GPS overlays,
streaming delivery and complete lifecycle acceptance remain pending.
