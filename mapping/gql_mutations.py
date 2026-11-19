import graphene
from core.gql.gql_mutations.base_mutation import BaseMutation
from core.schema import OpenIMISMutation
from mapping.access import require_capability
from mapping.jobs import start_sync


class MappingStartSyncMutation(BaseMutation):
    _mutation_class = "MappingStartSyncMutation"
    _mutation_module = "mapping"

    class Input(OpenIMISMutation.Input):
        source_instance = graphene.String(required=True)
        district_msr_id = graphene.Int(required=False)
        # Supports the existing published CoreMIS district picker without a new filter.
        district_uuid = graphene.String(required=False)

    @classmethod
    def _validate_mutation(cls, user, **data):
        require_capability(user, "sync_perms")

    @classmethod
    def _mutate(cls, user, **data):
        start_sync(user, data["source_instance"], district_id=data.get("district_msr_id"),
                   district_uuid=data.get("district_uuid"), client_mutation_id=data.get("client_mutation_id"))
        return None
