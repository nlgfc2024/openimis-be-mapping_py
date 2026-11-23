"""Mapping displays non-MSR geography and accepted local data with networking blocked."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from django.db import transaction
import graphene
from location.models import Location, GeographicFeature
from mapping.apps import MappingConfig
from mapping.schema import Query

class IndependentMappingTests(TestCase):
    def setUp(self):
        self.atomic=transaction.atomic();self.atomic.__enter__();self.addCleanup(self.rollback)
        district=Location.objects.filter(type='R',validity_to__isnull=True).first()
        self.feature=GeographicFeature.objects.create(source_instance='local-survey',external_type='survey-area',external_id='area-17',
            kind='district',name='Local survey',code='SURVEY17',district=district,location=district,
            geometry={'type':'FeatureCollection','features':[{'type':'Feature','properties':{'private':'fixture'},
                'geometry':{'type':'Polygon','coordinates':[[[33,-14],[34,-14],[34,-13],[33,-14]]]}}]},
            geometry_revision=1,publication_status='available')
        self.config=patch.multiple(MappingConfig,enabled=True,repository='coremis',view_perms=['view'],
            permitted_district_uuids=[str(district.uuid)],permitted_source_instances=['local-survey'])
        self.config.start();self.addCleanup(self.config.stop)
        self.scope=patch('location.models.allowed_micro_catchment_district_ids',return_value=None)
        self.scope_mock=self.scope.start();self.addCleanup(self.scope.stop)
        self.user=SimpleNamespace(is_anonymous=False,is_active=True,has_perms=lambda permissions:True)
        self.schema=graphene.Schema(query=Query)

    def rollback(self):
        transaction.set_rollback(True);self.atomic.__exit__(None,None,None)

    def test_non_msr_geography_and_local_geometry_work_offline(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Networking forbidden')):
            result=self.schema.execute('{mappingAreas(kind:"district"){totalCount items{id externalId name}}}',context_value=SimpleNamespace(user=self.user))
            self.assertFalse(result.errors)
            self.assertEqual(result.data['mappingAreas']['totalCount'],1)
            self.assertEqual(result.data['mappingAreas']['items'][0]['externalId'],'area-17')
            result=self.schema.execute('query($id:ID!){mappingGeometryAccess(referenceId:$id){status geojson}}',variable_values={'id':'geo:'+str(self.feature.pk)},context_value=SimpleNamespace(user=self.user))
            self.assertFalse(result.errors)
            self.assertEqual(result.data['mappingGeometryAccess']['status'],'available')
            self.assertEqual(result.data['mappingGeometryAccess']['geojson']['features'][0]['properties'],{})

    def test_revoked_district_scope_hides_direct_geometry_and_counts(self):
        self.scope_mock.return_value=set()
        result=self.schema.execute('{mappingAreas{totalCount}}',context_value=SimpleNamespace(user=self.user))
        self.assertEqual(result.data['mappingAreas']['totalCount'],0)
        result=self.schema.execute('query($id:ID!){mappingGeometryAccess(referenceId:$id){status}}',variable_values={'id':'geo:'+str(self.feature.pk)},context_value=SimpleNamespace(user=self.user))
        self.assertTrue(result.errors)
