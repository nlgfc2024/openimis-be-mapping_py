# Project household GPS layer — 25 November 2026

## Behaviour

The project's Boundary Map now passes its explicit UUID to the shared Mapping
component. Enrolled households appear as a separate green point layer with a
toggle, keyboard/click details, shared fit/zoom controls and Material UI pagination.
Only the current page is displayed. Details label GPS as a household location,
not an individual measurement; source accuracy and elevation have no invented
units or accuracy guarantee. Personal names, national IDs, phone numbers, source
household identities and full household JSON are not returned by the new query.

Household GPS can be displayed without a geographic publication or boundary
reference. Existing district and micro-catchment boundaries and geographic point
controls remain available independently. Membership of a programme/project does
not establish polygon containment or MSR-verified village coverage.

## Local, authorised API

```graphql
query ProjectHouseholds($project: UUID!, $offset: Int!, $limit: Int!) {
  mappingProjectHouseholds(projectId: $project, offset: $offset, limit: $limit) {
    totalCount
    scopedCount
    items { id code name kind latitude longitude accuracy elevation syncedAt }
  }
}
```

The optional CoreMIS repository adapter reads existing local models only. Mapping
does not import MSR ETL, fetch upstream data, hold MSR credentials or enrol people.

The query requires all of:

- Mapping enabled, with configured view, project and GPS capabilities satisfied;
- the project overlay enabled;
- the host's project search, household search and beneficiary search rights;
- an active project and programme in a configured, accessible CoreMIS district;
- existing host household and beneficiary row security.

Permission and project-scope failures return no household counts or coordinates.
Counts are calculated only inside the authorised enrolment/household scope.
The page uses the existing bounded Mapping page limits (50 default, configured
maximum no greater than 200).

For group programmes, active project group-beneficiary enrolments resolve to their
household. For individual programmes, active enrolled beneficiaries resolve through
existing active `GroupIndividual` links. Both exclude deleted records, inactive
beneficiaries and beneficiaries belonging to another programme. An `Exists` query
deduplicates households, including when several enrolled individuals share one
household. No marker is invented from a member or village without household GPS.

GPS must have the household coordinate type, a source tag matching the household,
and numeric WGS84 latitude/longitude within valid bounds. Missing/invalid GPS
reduces usable-point count but does not hide the number of authorised enrolled
households. Imported zero coordinates are not silently moved or classified as
verified. Point availability does not imply surveyed accuracy.

## Activation

```bash
python manage.py configure_coremis_mapping --enable-project-overlay --apply
```

This preserves configured view/project/GPS rights and scopes and copies GPS
capability configuration to `fe-mapping.gpsRights`. It sets the backend overlay
flag and `fe-mapping.projectOverlayEnabled`. It does not grant roles, change
programme enrolments or change importer credentials. Use
`--disable-project-overlay` to disable the layer. Restart the backend and reload
the frontend after updating configuration/packages.

Existing household/upload JSON remains subject to its existing host access rules;
these controls describe the new Mapping query, not a replacement for host-wide
JSON-field access policy.

## Pilot enrolment and approval state

The requested project, “Dedza-mtantho-hospot-Land resource-Phase-1 - Kamenya”,
belongs to the GROUP programme Phase-1 and has a target of 20 beneficiaries.
Its supplied workbook has 49 MAIN rows and 10 RESERVE rows.

Ten distinct MAIN households were selected in workbook order, requiring an
APPLIED/verified stored validation row, an active primary-worker link matching
the workbook and stored household GPS. None had an active beneficiary record in
this programme, so programme registration is needed before project enrolment.

The deployment has
`social_protection.gql_check_group_beneficiary_crud=true`. Ten normal
`GroupBeneficiaryService.create` approval requests were therefore submitted.
No approval setting was disabled and no programme status was forced. At the
initial live check all ten requests were RECEIVED, the selected households had no
active programme beneficiaries yet, and the project correctly returned zero
household markers. This is pending approval, not evidence of missing GPS.

After approval, enrol the ten active group beneficiaries through the existing
`ProjectEnrollmentService.GROUP` service, preserving all current project IDs in
the submitted selection. Its API replaces the selection, so omitting existing
IDs would unenrol them. The existing service enforces programme/status eligibility,
target capacity and exclusive-enrolment rules; no Mapping code changes those rules.

## Verification

- Portable Mapping schema/access suite: 19 tests passed.
- Five isolated PostgreSQL tests passed for deduplication, individual household
  resolution, invalid GPS, deleted enrolments/projects, source isolation,
  host/Mapping permissions, district/household scope and pagination.
- Existing geospatial/import coordination suite: 102 tests passed.
- Frontend module/projection/publication checks and host UI fixtures passed,
  including project UUID forwarding, no GPS query without rights, independent
  household toggling, keyboard details, removal on refresh and point-only display
  without boundary references.
- Django checks passed and no Mapping model migration is needed.
- Mapping and project frontend package builds and the full CoreMIS frontend
  production build passed. The host ESLint plugin remains disabled; standalone
  undefined-variable checks passed for the Mapping source.
- Live reads with the real configured actor succeeded without upstream HTTP;
  removing GPS capability denied the entire household query, including counts.
- All ten selected pilot households are visible under the actual configured
  actor's existing household scope; no extra location or GPS role grants were made.

At the initial check, live display of the ten requested project household markers
was still dependent on programme approval and project enrolment. The subsequent
operator confirmation and live verification are recorded below; automated fixtures
alone did not establish that milestone.

### Approval routing correction

The initial ten requests were visible in All tasks but had no executor group;
their RECEIVED status disabled the existing approval buttons. The Social
Protection frontend also omitted the `GroupBeneficiaryService` task contribution.
That source and its household/programme/status preview are now registered in the
local Social Protection frontend repository, based on the assembly's installed
commit to preserve its existing integration.

The existing beneficiary approval group `001` now includes this source, preserving
its ALL policy and existing executors. The ten requests were assigned to that group
using the normal task service and are ACCEPTED (assigned and ready for review),
not approved. The existing task query confirms all ten are visible to the reviewer;
none is COMPLETED and no approval vote has been recorded by this change. Future
requests use the host's existing automatic source-to-group routing.

After reloading the frontend, use Tasks Management → All tasks, filter by Task
Group `001` and status ACCEPTED, open the eye icon and use the check-mark button
to approve. `Entity: None` is normal for these create requests: the programme
beneficiary entity does not exist until approval.

### Live pilot verification after operator enrolment

The operator subsequently enrolled the households and supplied project-map
screenshots showing the household layer and “10 of 10 enrolled households have
usable stored GPS.” A fresh read-only backend check confirmed:

- 10 active project group-beneficiary enrolments;
- 10 authorised household records with usable GPS and 10 distinct household IDs;
- exactly one distinct stored coordinate pair across those ten households;
- the project/MTANTHO match remains intact, with 66 verified village memberships.

All ten household symbols therefore occupy the same map position. The single
visible circle is overplotting of ten records, not evidence of a lost enrolment
or a one-record query limit. Geographic reference points remain independently
unavailable (0 of 67); household GPS does not supply village coordinates.

The boundary-plus-enrolled-household display is now demonstrated by the operator
screenshots and backend counts. Individual household locations cannot be visually
distinguished with the current symbols when their source coordinates are equal.
The frontend now provides a count badge and a household chooser to make coincident
records inspectable. Grouping uses exact stored coordinates on the current page;
nearby coordinates and geographic reference markers are not merged. Clicking the
badge or pressing Enter/Space opens the selector and the chosen household's own
details. Removing a record or hiding the layer clears its details. Counts and text
remain readable when zooming. This is a display change only; changing or spreading
the actual coordinates would misrepresent the stored data.
The common coordinate itself does not establish why MSR households share a position
or prove surveyed household accuracy; that remains a source-data review if distinct
household positions were expected.
