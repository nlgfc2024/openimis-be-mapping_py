# District catchment overview and drill-down

## Operator flow

1. Select a district in the existing CoreMIS district picker and, when necessary,
   select its source match. The map shows its available district outline and all
   authorised micro-catchments with accepted local geometry, in different colours.
2. Click a catchment polygon or focus it and press Enter/Space. The selected shape
   is highlighted, its name and publication status are shown, and the dropdown
   follows the map selection. Choosing the dropdown performs the same action.
3. The view fits the selected catchment's complete geometry. The district and
   other catchments remain context layers. “Fit all layers” shows their full
   extent; “Fit map” refits the selected catchment. Clicking the selected shape
   again also refits it.
4. With project mapping rights, enable “Explore catchment projects”. Projects are
   resolved through the explicit CoreMIS micro-catchment match, not containment.
   A single linked project is selected automatically. With multiple projects,
   select one from the project dropdown. Clearing the selection removes its
   household layer. The existing GPS rights and overlay flag are still required
   to read enrolled household GPS.
5. “Back to district” clears catchment/project selection and restores the overview
   with all available catchments visible. Project-page maps remain pinned to their
   own catchment and project rather than switching to unrelated project records.

Catchments without accepted geometry stay in the dropdown and publication list,
marked unavailable. They can be selected to inspect their status; the map retains
available context instead of inventing a boundary or fitting a missing polygon.
Individual read failures are labelled for retry.

## Geometry and publication semantics

Fitting changes only the display transform. It does not expand, move, intersect,
clip to the district outline, or modify the stored boundary. District overview
extent includes available catchment geometry outside the district outline.
Drill-down fits all parts of the selected geometry; GPS outside that extent is
still retained and can be viewed using “Fit all layers”.

Source-area association labels are preserved in the map legend, polygon title,
publication list and selected publication details. An accepted geometry is not
promoted into verified village membership or an authoritative catchment boundary.
Existing revision, retention and publication-warning semantics remain in use.

## Reads, pagination and access

The existing `mappingAreas` metadata query is paged to completion instead of
displaying only the first catchment page. A failed/inconsistent metadata page is
reported as an incomplete list rather than presented as the complete district.
Cancelled district/source/permission requests cannot publish stale collections.

Available local boundaries are read through existing `mappingGeometryAccess`,
with at most four requests in flight. Authoritatively unavailable metadata does
not cause an unnecessary geometry read. Failed individual geometry reads do not
prevent the other accepted shapes from appearing.

The new optional CoreMIS read is:

```graphql
query CatchmentProjects($reference: ID!, $offset: Int!, $limit: Int!) {
  mappingCatchmentProjects(referenceId: $reference, offset: $offset, limit: $limit) {
    totalCount
    items { id code name status }
  }
}
```

It requires Mapping view/project rights, the host project-search permission and
an authorised micro-catchment reference. Projects must be live, belong to a live
programme, have the explicit live CoreMIS micro-catchment match and be within the
reference's authorised district. Unmatched or inconsistent matches return no
projects. GPS and beneficiary permissions are not replaced by project-list access:
the selected project's household points still use `mappingProjectHouseholds`.

Only one selected project's household page is requested at a time. Existing
same-coordinate count badges, household selection and page-scoped counts remain
unchanged. Disabling project exploration, clearing the project, changing the
catchment or returning to the overview clears that project's household points.

No new MSR endpoint, source synchronization, model migration, enrolment mutation,
permission grant or tile/basemap service is introduced in this chunk. The existing
CoreMIS components, date formatting and SVG renderer are reused. All map reads
remain local and source-neutral; MSR-specific imports remain in MSR ETL.

## Verification — 26 November 2026

- Portable backend schema/access suite: 20 tests passed.
- Isolated PostgreSQL project/GPS suite: 6 tests passed, including explicit
  catchment-match project discovery and restricted reference access.
- Existing geospatial/import regression suite: 102 tests passed.
- Frontend helper checks cover multi-page completion, cancellation, inconsistent
  paging, bounded concurrency, colours, selected-geometry fitting and unchanged
  cross-district source coordinates.
- Host UI fixtures cover a 51-catchment/two-page overview, simultaneous shapes,
  unavailable records, polygon/dropdown/keyboard selection, refitting, linked
  project/GPS exploration, clearing and Back behaviour, denied project/GPS reads
  for map-only users, and safe handling of an incomplete overview read.
- Existing household-marker and project compatibility UI checks passed.
- Django checks passed and no Mapping model migration was detected.
- Mapping package and full CoreMIS frontend production builds passed. The host
  ESLint plugin remains disabled; standalone undefined-variable checks passed.

A live read-only check found all **48 Dedza catchments**, with **25 available**
geometries and **23 unavailable**. MTANTHO remains matched and labelled as a
source-area association, with one authorised linked project. That project's
current authorised household scope is **8 households with usable GPS**. This is
the current enrolment state; no records were enrolled, removed or otherwise
modified by the check. Upstream HTTP was blocked and no upstream requests occurred.

Restart the backend and reload the frontend together after installing Mapping
0.6.0. Browser acceptance remains an operator step: select Dedza, compare the
overview/dropdown, click MTANTHO, check its publication/project/household layers,
then use Back to district.
