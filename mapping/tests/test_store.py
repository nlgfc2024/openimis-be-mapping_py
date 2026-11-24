"""Mapping displays non-MSR geography and accepted local data with networking blocked."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from django.db import transaction
import graphene
from location.models import Location, GeographicFeature, GeographicMembership
from django.utils import timezone
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

    def test_points_use_verified_membership_and_validate_coordinates(self):
        def feature(key, kind='village', status='available', lat=-14.1, lng=33.1, source='local-survey'):
            return GeographicFeature.objects.create(source_instance=source,external_type=kind,external_id=key,
                kind=kind,name=key,code=key,district=self.feature.district,latitude=lat,longitude=lng,point_status=status)
        area=feature('micro','micro_catchment')
        area.geometry=self.feature.geometry
        area.publication_status='available'
        area.geometry_revision=1
        area.save()
        good=feature('A-good')
        zero=feature('B-zero',status=None,lat=0,lng=0)
        missing=feature('C-missing',lng=None)
        invalid=feature('D-invalid',lat=91)
        unavailable=feature('E-unavailable',status=' Unavailable ')
        uncertain=feature('F-unspecified',status=None)
        nan=feature('G-nan',lat=float('nan'))
        infinite=feature('H-infinite',lng=float('inf'))
        unrelated=feature('inside-polygon-but-not-a-member',lat=-13.8,lng=33.5)
        other=feature('other-source',source='other-source')
        for child in (good,zero,missing,invalid,unavailable,uncertain,nan,infinite,other):
            GeographicMembership.objects.create(parent=area,child=child,verified_at=timezone.now())
        def query(offset=0,limit=50):
            result=self.schema.execute('query($id:ID!,$offset:Int!,$limit:Int!){mappingPoints(areaReferenceId:$id,offset:$offset,limit:$limit){totalCount scopedCount items{externalId latitude longitude pointStatus}}}',
                variable_values={'id':'geo:'+str(area.pk),'offset':offset,'limit':limit},context_value=SimpleNamespace(user=self.user))
            self.assertFalse(result.errors)
            return result.data['mappingPoints']
        data=query()
        self.assertEqual(data['totalCount'],4)
        self.assertEqual(data['scopedCount'],9)
        self.assertEqual({row['externalId'] for row in data['items']},{'micro','A-good','B-zero','F-unspecified'})
        self.assertEqual(len(query(1,2)['items']),2)
        self.assertEqual(query(4,2)['items'],[])
        self.scope_mock.return_value=set()
        result=self.schema.execute('query($id:ID!){mappingPoints(areaReferenceId:$id){totalCount scopedCount}}',
            variable_values={'id':'geo:'+str(area.pk)},context_value=SimpleNamespace(user=self.user))
        self.assertTrue(result.errors)
        self.assertIsNone(result.data['mappingPoints'])

    def test_geometry_freshness_fields_are_local_and_consistent(self):
        now=timezone.now()
        self.feature.observed_revision=3
        self.feature.geometry_revision=2
        self.feature.geometry_updated_at=now
        self.feature.synced_at=now
        self.feature.refresh_status='delivery_unavailable'
        self.feature.save()
        with patch('requests.sessions.Session.request',side_effect=AssertionError('Networking forbidden')):
            result=self.schema.execute('query($id:ID!){mappingGeometryAccess(referenceId:$id){status revision observedRevision acceptedAt importedAt refreshStatus}}',
                variable_values={'id':'geo:'+str(self.feature.pk)},context_value=SimpleNamespace(user=self.user))
        self.assertFalse(result.errors)
        state=result.data['mappingGeometryAccess']
        self.assertEqual(state['status'],'available')
        self.assertEqual((state['revision'],state['observedRevision']),('2','3'))
        self.assertEqual(state['refreshStatus'],'delivery_unavailable')
        self.assertIsNotNone(state['acceptedAt'])
        self.assertIsNotNone(state['importedAt'])
