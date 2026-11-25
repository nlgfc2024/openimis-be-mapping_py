import uuid
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import graphene
from django.db import transaction
from django.test import override_settings
from core.models import User
from individual.models import Group, Individual, GroupIndividual
from social_protection.models import BenefitPlan, GroupBeneficiary, Beneficiary
from project_social_protection.models import (Project,Activity,GroupBeneficiaryProjectEnrollment,
    BeneficiaryProjectEnrollment)
from location.models import Location
from mapping.apps import MappingConfig
from mapping.schema import Query


class ProjectHouseholdTests(TestCase):
    def setUp(self):
        self.atomic=transaction.atomic();self.atomic.__enter__();self.addCleanup(self.rollback)
        self.actor=User.objects.filter(i_user__isnull=False).first()
        permission=patch.object(self.actor,'has_perms',return_value=True)
        permission.start();self.addCleanup(permission.stop)
        security=override_settings(ROW_SECURITY=False)
        security.enable();self.addCleanup(security.disable)
        self.district=Location.objects.filter(type='R',validity_to__isnull=True).first()
        self.plan=self.make(BenefitPlan,code='MAPGPS',name='Fixture',type='GROUP')
        activity=self.make(Activity,name='Mapping fixture')
        self.project=self.make(Project,name='Mapping fixture',benefit_plan=self.plan,activity=activity,
            location=self.district,target_beneficiaries=20,working_days=30)
        config=patch.multiple(MappingConfig,enabled=True,repository='coremis',view_perms=['view'],
            project_perms=['project'],gps_perms=['gps'],project_overlay_enabled=True,
            permitted_district_uuids=[str(self.district.uuid)])
        config.start();self.addCleanup(config.stop)
        self.scope=patch('location.models.allowed_micro_catchment_district_ids',return_value=None)
        self.scope_mock=self.scope.start();self.addCleanup(self.scope.stop)
        self.schema=graphene.Schema(query=Query)
        self.context=SimpleNamespace(user=self.actor)

    def rollback(self):
        transaction.set_rollback(True);self.atomic.__exit__(None,None,None)

    def make(self,model,**fields):
        obj=model(id=uuid.uuid4(),user_created=self.actor,user_updated=self.actor,**fields)
        model.objects.bulk_create([obj])
        return obj

    def household(self,code,gps=True,**quality):
        ext={'data_source':'ubr'}
        if gps:ext['household_gps']={'latitude':-14,'longitude':33,'coordinate_type':'household',
            'source_type':'ubr','accuracy':5,'imported_at':'2026-11-25T10:00:00',**quality}
        return self.make(Group,code=code,location=self.district,json_ext=ext)

    def enrol(self,group,**extra):
        beneficiary=self.make(GroupBeneficiary,group=group,benefit_plan=self.plan,status=extra.pop('status','ACTIVE'),**extra)
        return self.make(GroupBeneficiaryProjectEnrollment,project=self.project,group_beneficiary=beneficiary)

    def query(self,project=None,**variables):
        return self.schema.execute('query($id:UUID!,$offset:Int,$limit:Int){mappingProjectHouseholds(projectId:$id,offset:$offset,limit:$limit){totalCount scopedCount items{id code kind latitude longitude}}}',
            variable_values={'id':str((project or self.project).pk),'offset':0,'limit':50,**variables},context_value=self.context)

    def test_enrolled_households_deduplicate_and_invalid_gps_is_excluded(self):
        group=self.household('A');self.enrol(group);self.enrol(group)
        self.enrol(self.household('missing',gps=False))
        self.enrol(self.household('invalid',latitude=91))
        self.enrol(self.household('string',latitude='-14'))
        self.enrol(self.household('wrong-source',source_type='other'))
        self.household('not-enrolled')
        deleted=self.enrol(self.household('deleted-enrolment'))
        GroupBeneficiaryProjectEnrollment.objects.filter(pk=deleted.pk).update(is_deleted=True)
        inactive=self.household('suspended');self.enrol(inactive,status='SUSPENDED')
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No HTTP')):
            result=self.query()
        self.assertFalse(result.errors,str(result.errors))
        self.assertEqual(result.data['mappingProjectHouseholds']['totalCount'],1)
        self.assertEqual(result.data['mappingProjectHouseholds']['scopedCount'],5)
        self.assertEqual(result.data['mappingProjectHouseholds']['items'][0]['code'],'A')

    def test_individual_beneficiaries_share_one_household_marker(self):
        self.plan.type='INDIVIDUAL';BenefitPlan.objects.filter(pk=self.plan.pk).update(type='INDIVIDUAL')
        group=self.household('shared')
        for index in range(2):
            individual=self.make(Individual,first_name='Fixture',last_name='Only',dob='1990-01-01',location=self.district)
            self.make(GroupIndividual,group=group,individual=individual)
            beneficiary=self.make(Beneficiary,individual=individual,benefit_plan=self.plan,status='ACTIVE')
            self.make(BeneficiaryProjectEnrollment,project=self.project,beneficiary=beneficiary)
        result=self.query()
        self.assertFalse(result.errors,str(result.errors))
        self.assertEqual(result.data['mappingProjectHouseholds']['totalCount'],1)

    def test_revoke_permissions_district_and_household_scope_hides_counts(self):
        self.enrol(self.household('allowed'))
        with patch.object(self.actor,'has_perms',return_value=False):
            self.assertTrue(self.query().errors)
        self.scope_mock.return_value=set()
        self.assertTrue(self.query().errors)
        self.scope_mock.return_value=None
        with patch.object(Group,'get_queryset',side_effect=lambda qs,user:qs.none()):
            result=self.query()
            self.assertFalse(result.errors)
            self.assertEqual(result.data['mappingProjectHouseholds']['scopedCount'],0)

    def test_pagination_and_deleted_project(self):
        self.enrol(self.household('A'));self.enrol(self.household('B'))
        result=self.query(offset=1,limit=1)
        self.assertFalse(result.errors,str(result.errors))
        self.assertEqual(result.data['mappingProjectHouseholds']['totalCount'],2)
        self.assertEqual(result.data['mappingProjectHouseholds']['items'][0]['code'],'B')
        Project.objects.filter(pk=self.project.pk).update(is_deleted=True)
        self.assertTrue(self.query().errors)

    def test_host_permissions_and_configured_district_scope_are_required(self):
        from project_social_protection.apps import ProjectSocialProtectionConfig
        from individual.apps import IndividualConfig
        from social_protection.apps import SocialProtectionConfig
        self.enrol(self.household('allowed'))
        for denied in (ProjectSocialProtectionConfig.gql_project_search_perms[0],
                       IndividualConfig.gql_group_search_perms[0],
                       SocialProtectionConfig.gql_beneficiary_search_perms[0]):
            with patch.object(self.actor,'has_perms',side_effect=lambda rights:denied not in rights):
                self.assertTrue(self.query().errors)
        with patch.object(MappingConfig,'permitted_district_uuids',[]):
            self.assertTrue(self.query().errors)
