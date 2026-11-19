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
