from types import SimpleNamespace
from unittest.mock import Mock, patch
import graphene
from django.test import SimpleTestCase

from mapping.apps import DEFAULT_CONFIG, MappingConfig
from mapping.schema import Query


class MappingSchemaTests(SimpleTestCase):
    def setUp(self):
        original = {key: getattr(MappingConfig, key) for key in DEFAULT_CONFIG}
        self.addCleanup(MappingConfig.load_config, original)
        MappingConfig.load_config({"enabled": True, "view_perms": ["test.mapping.view"]})
        self.user = Mock(is_anonymous=False)
        self.user.has_perms.return_value = True
        self.context = SimpleNamespace(user=self.user)
        self.schema = graphene.Schema(query=Query)
        self.repo = Mock()
        patcher = patch("mapping.schema.get_repository", return_value=self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)

    def query(self, query):
        return self.schema.execute(query, context_value=self.context)

    def test_disabled_module_denies_without_constructing_repository(self):
        MappingConfig.enabled = False
        result = self.query("{mappingReferences{totalCount}}")
        self.assertTrue(result.errors)
        self.repo.list_references.assert_not_called()

    def test_project_households_require_all_capabilities_and_overlay_before_counts(self):
        query='{mappingProjectHouseholds(projectId:"11111111-1111-4111-8111-111111111111"){totalCount}}'
        with patch.multiple(MappingConfig,project_perms=['project'],gps_perms=['gps'],project_overlay_enabled=True):
            for denied in ('test.mapping.view','project','gps'):
                self.user.has_perms.side_effect=lambda rights: denied not in rights
                self.assertTrue(self.query(query).errors)
                self.repo.project_households.assert_not_called()
            self.user.has_perms.side_effect=None
            self.user.has_perms.return_value=True
            self.repo.project_households.return_value=([],0,0)
            self.assertFalse(self.query(query).errors)
            self.repo.project_households.reset_mock()
            MappingConfig.project_overlay_enabled=False
            self.assertTrue(self.query(query).errors)
            self.repo.project_households.assert_not_called()

    def test_project_household_page_validation_and_minimal_payload(self):
        with patch.multiple(MappingConfig,project_perms=['project'],gps_perms=['gps'],project_overlay_enabled=True):
            self.repo.project_households.return_value=([{'id':'household:1','latitude':-14,'longitude':33,'kind':'household'}],1,2)
            result=self.query('{mappingProjectHouseholds(projectId:"11111111-1111-4111-8111-111111111111",limit:25){totalCount scopedCount items{id latitude longitude kind}}}')
            self.assertFalse(result.errors)
            self.assertEqual(result.data['mappingProjectHouseholds']['scopedCount'],2)
            for argument in ('offset:-1','limit:201','limit:0'):
                self.assertTrue(self.query('{mappingProjectHouseholds(projectId:"11111111-1111-4111-8111-111111111111",'+argument+'){totalCount}}').errors)

    def test_catchment_projects_require_view_project_scope_and_correct_kind(self):
        query='{mappingCatchmentProjects(referenceId:"geo:20",limit:25){totalCount items{name status}}}'
        with patch.object(MappingConfig,'project_perms',['project']):
            self.repo.get_reference.return_value=SimpleNamespace(kind='micro_catchment')
            self.repo.catchment_projects.return_value=([{'name':'Authorised project','status':'PREPARATION'}],1)
            result=self.query(query)
            self.assertFalse(result.errors)
            self.assertEqual(result.data['mappingCatchmentProjects']['totalCount'],1)
            self.repo.catchment_projects.reset_mock()
            self.user.has_perms.side_effect=lambda rights:'project' not in rights
            self.assertTrue(self.query(query).errors)
            self.repo.catchment_projects.assert_not_called()
            self.user.has_perms.side_effect=None
            self.repo.get_reference.return_value=None
            self.assertTrue(self.query(query).errors)
            self.repo.catchment_projects.assert_not_called()
            self.repo.get_reference.return_value=SimpleNamespace(kind='village')
            self.assertTrue(self.query(query).errors)
            self.repo.catchment_projects.assert_not_called()

    def test_unallocated_capability_fails_closed(self):
        MappingConfig.view_perms = []
        self.assertTrue(self.query("{mappingReferences{totalCount}}").errors)
        self.repo.list_references.assert_not_called()

    def test_user_permission_and_anonymous_access_checked(self):
        for anonymous, permission in ((True, True), (False, False)):
            self.user.is_anonymous = anonymous
            self.user.has_perms.return_value = permission
            self.assertTrue(self.query("{mappingReferences{totalCount}}").errors)
        self.repo.list_references.assert_not_called()

    def test_filtered_pages_return_only_repository_results_and_totals(self):
        self.repo.list_references.return_value = ([SimpleNamespace(id=3523,msr_id=265,code="213009",name="MTANTHO")], 1)
        result = self.query('{mappingReferences(sourceInstance:"msr-malawi",districtMsrId:"13",msrType:"catchments",offset:0,limit:20){totalCount items{id msrId code}}}')
        self.assertFalse(result.errors)
        self.assertEqual(result.data["mappingReferences"], {"totalCount":1,"items":[{"id":"3523","msrId":"265","code":"213009"}]})
        self.repo.list_references.assert_called_once_with(self.user, {"source_instance":"msr-malawi","district_msr_id":"13","msr_type":"catchments"},0,20)

    def test_page_limits_rejected_before_query(self):
        for args in ("limit:201", "offset:-1", "limit:0"):
            self.assertTrue(self.query("{mappingReferences("+args+"){totalCount}}").errors)
        self.repo.list_references.assert_not_called()

    def test_point_page_is_scoped_to_visible_area_and_bounded(self):
        area=SimpleNamespace(pk=10,kind='micro_catchment')
        self.repo.get_reference.return_value=area
        self.repo.points.return_value=([SimpleNamespace(id=11,latitude=-14.0,longitude=33.0)],1,67)
        result=self.query('{mappingPoints(areaReferenceId:"geo:10",offset:25,limit:25){totalCount scopedCount items{latitude longitude}}}')
        self.assertFalse(result.errors)
        self.assertEqual(result.data['mappingPoints'],{'totalCount':1,'scopedCount':67,'items':[{'latitude':-14.0,'longitude':33.0}]})
        self.repo.points.assert_called_once_with(self.user,area,25,25)
        self.repo.points.reset_mock()
        self.assertTrue(self.query('{mappingPoints(areaReferenceId:"geo:10",limit:201){totalCount}}').errors)
        self.repo.points.assert_not_called()

    def test_hidden_or_wrong_kind_area_cannot_expose_point_counts(self):
        for area in (None,SimpleNamespace(kind='village')):
            self.repo.get_reference.return_value=area
            self.assertTrue(self.query('{mappingPoints(areaReferenceId:"geo:10"){totalCount scopedCount}}').errors)
        self.repo.points.assert_not_called()

    def test_point_query_checks_view_permission_first(self):
        self.user.has_perms.return_value=False
        self.assertTrue(self.query('{mappingPoints(areaReferenceId:"geo:10"){totalCount}}').errors)
        self.repo.get_reference.assert_not_called()
        self.repo.points.assert_not_called()

    def test_existing_district_picker_uuid_is_forwarded(self):
        self.repo.list_references.return_value = ([], 0)
        result = self.query('{mappingReferences(districtUuid:"reviewed-local-district"){totalCount}}')
        self.assertFalse(result.errors)
        self.repo.list_references.assert_called_once_with(self.user, {"district_uuid": "reviewed-local-district"}, 0, 100)

    def test_direct_id_scope_cannot_be_bypassed_for_geometry(self):
        self.repo.get_reference.return_value = None
        result = self.query('{mappingGeometryAccess(referenceId:"3523"){status}}')
        self.assertTrue(result.errors)
        self.repo.geometry.assert_not_called()

    def test_geometry_returns_current_state_and_stable_id(self):
        ref = SimpleNamespace(pk=3523)
        self.repo.get_reference.return_value = ref
        self.repo.geometry.return_value = {"status":"unavailable","revision":"2","geojson":None}
        result = self.query('{mappingGeometryAccess(referenceId:"3523"){referenceId status revision geojson}}')
        self.assertFalse(result.errors)
        self.assertEqual(result.data["mappingGeometryAccess"], {"referenceId":"3523","status":"unavailable","revision":"2","geojson":None})

    def test_invalid_id_rejected_before_repository_lookup(self):
        self.assertTrue(self.query('{mappingReference(referenceId:"not-an-id"){id}}').errors)
        self.repo.get_reference.assert_not_called()

    def test_only_micro_catchments_have_verified_village_operation(self):
        self.repo.get_reference.return_value = SimpleNamespace(msr_type="districts",is_micro=None)
        self.assertTrue(self.query('{mappingVerifiedVillages(catchmentReferenceId:"1"){totalCount}}').errors)
        self.repo.verified_villages.assert_not_called()

    def test_complete_empty_verified_village_page_is_valid(self):
        ref=SimpleNamespace(msr_type="catchments",is_micro=True)
        self.repo.get_reference.return_value = ref
        self.repo.verified_villages.return_value = ([],0)
        result=self.query('{mappingVerifiedVillages(catchmentReferenceId:"3523"){totalCount items{id}}}')
        self.assertFalse(result.errors)
        self.assertEqual(result.data["mappingVerifiedVillages"], {"totalCount":0,"items":[]})
