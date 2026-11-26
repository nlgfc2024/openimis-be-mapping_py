"""Project/household tests isolated from live enrolments and identities."""
import unittest
import uuid
from django.db import connection


def run():
    from individual.models import Group,Individual,GroupIndividual
    from social_protection.models import BenefitPlan,GroupBeneficiary,Beneficiary
    from project_social_protection.models import Project,Activity,GroupBeneficiaryProjectEnrollment,BeneficiaryProjectEnrollment
    from location.models import MicroCatchment,GeographicFeature
    if connection.vendor!='postgresql' or connection.in_atomic_block:
        raise RuntimeError('Use PostgreSQL outside a transaction')
    quoted=connection.ops.quote_name('mapping_households_'+uuid.uuid4().hex)
    with connection.cursor() as cursor:
        cursor.execute('SHOW search_path');original=cursor.fetchone()[0]
        cursor.execute('CREATE SCHEMA '+quoted)
        cursor.execute('SET search_path TO '+quoted+', public')
        for model in (Group,Individual,GroupIndividual,BenefitPlan,GroupBeneficiary,Beneficiary,
                      Project,Activity,GroupBeneficiaryProjectEnrollment,BeneficiaryProjectEnrollment,MicroCatchment,GeographicFeature):
            table=connection.ops.quote_name(model._meta.db_table)
            cursor.execute('CREATE TABLE '+quoted+'.'+table+' (LIKE public.'+table+' INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)')
    try:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('mapping.tests.test_project_households'))
        if not result.wasSuccessful():raise RuntimeError('Project household tests failed')
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('search_path',%s,false)",[original])
            cursor.execute('DROP SCHEMA '+quoted+' CASCADE')
