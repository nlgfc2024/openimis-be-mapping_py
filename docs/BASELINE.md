# Recorded extraction baseline

Recorded 19 November 2026. Source credentials, runtime configuration values and beneficiary data are excluded.

| Repository | Baseline commit |
| --- | --- |
| backend/openimis-be-location_py | `41d4523e88117544893f58d2af92a7bf504f211a` |
| backend/openimis-be-msr_etl_py | `e47893ec8551208282bdc4a543949c21209afb81` |
| backend/openimis-be-project_social_protection_py | `1c06a13a2253cbfbac35e28842a063d66fff1279` |
| backend/openimis-be_py | `0db19a57d419a0ef5dc3f2731c184fb56a159ad8` |
| frontend/openimis-fe-location_js | `61e494a660db0d89ad7beca46844e8428933e302` |
| frontend/openimis-fe-project_social_protection_js | `ebac50b5862562b64b9fb4b4acef60694a5399be` |
| frontend/openimis-fe_js | `8e6a34a7144052c267d8ed8a221f03c1cf50b2e7` |
| openimis-dist_dkr | `c9b7b5e23a041d2ad9f8c4cac8281e3ec6eb808a` |

## Storage and interface ownership

- CoreMIS reference/membership tables and IDs stay in location; source writes remain in MSR ETL.
- Existing reviewed MTANTHO link and independently configured CoreMIS GVHs are preserved.
- Last verified live membership response for MTANTHO was empty; do not invent source coverage.
- CoreMIS assembly manifests already contain local payroll/project/location/MSR ETL entries. Those user configurations were not overwritten or committed as part of the pilot baseline.
- Public source packages contain no ModuleConfiguration exports, tokens, signed URLs or private data.

## Source specification checksums

- `CoreMIS_Mapping_Module_Development_Specification.pdf`: SHA-256 `9b47db2aa820236a725e7f0c6a31ad021af8037736aa8d56e80ce63040bd2ad2`
- `CoreMIS_openIMIS_Mapping_Module_Implementation_Guide.docx`: SHA-256 `6e0ad7b8b8aed0db90fedf4bf032f027e3bde9ecacf686599e9b7d4afeb08f9c`

## Tested host runtime

| Component | Version |
| --- | --- |
| Python | `3.11.15` |
| Django | `4.2.30` |
| graphene | `2.1.9` |
| graphene-django | `2.16.0` |
| Node | `v24.19.0` |
| React | `17.0.2` |
| React Redux | `7.2.9` |
| Material UI | `4.12.4` |
| Frontend core | `1.4.0` |

## Assembly registration checksums

These describe the working local manifests after adding mapping; pre-existing user changes remain in place.

- `backend/openimis-be_py/openimis.json`: SHA-256 `c227b3e8fc1abbea7105c3e7eca621259265e23ce8e071d75cde68f66ddeaeb4`
- `frontend/openimis-fe_js/openimis.json`: SHA-256 `55ccfe99e9ba19c1fc35710cc9cf69337577af258680ae2288d8ed0928e755a2`
- `frontend/openimis-fe_js/yarn.lock`: SHA-256 `09a1a917ddad1a197d5de0b0d6164f05cc658f59ff786ed54f9d1cb46a75b989`
- `frontend/openimis-fe-mapping_js/package-lock.json`: SHA-256 `54cba54fa2bb53acb14bf4e8b7ae60d84df487afa71558c2f9b206c1cbe630ed`
