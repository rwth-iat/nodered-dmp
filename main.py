from aas_python_http_client import ApiClient, Configuration, AssetAdministrationShellRepositoryAPIApi, SubmodelRepositoryAPIApi
from aas_python_http_client.util import string_to_base64url
from basyx.aas import model

configuration = Configuration()
configuration.host = "http://localhost:8080/api/v3.0"

api_client = ApiClient(configuration=configuration)

aasRepoClient = AssetAdministrationShellRepositoryAPIApi(api_client=api_client)

# query all asset administration shells
all_aas = aasRepoClient.get_all_asset_administration_shells().result
print(all_aas)

exit(1)
# # query specific asset administration shell
# aas = aasRepoClient.get_asset_administration_shell_by_id(
#     string_to_base64url('https://acplt.org/Test_AssetAdministrationShell'))
# print(aas)
#
# # query asset information
# aas_info = aasRepoClient.get_asset_information_aas_repository(
#     string_to_base64url('https://acplt.org/Test_AssetAdministrationShell'))
# print(aas_info)

aas_name = "http://acplt.org/Test_AAS"
if aas_name not in [aas.id for aas in all_aas]:
    aas_info = model.AssetInformation(asset_kind=model.AssetKind.INSTANCE,
                                      global_asset_id='http://acplt.org/Test_Asset1')

    # create a new asset administration shell
    new_aas = model.AssetAdministrationShell(aas_info, aas_name)
    aasRepoClient.post_asset_administration_shell(new_aas)

# query specific asset administration shell
aas = aasRepoClient.get_asset_administration_shell_by_id(
    string_to_base64url('http://acplt.org/Test_AAS'))
print(aas)

#aasRepoClient.delete_asset_administration_shell_by_id(string_to_base64url(aas_name))

#
# submodelRepoClient = SubmodelRepositoryAPIApi(api_client=api_client)
#
# # query all submodels
# all_submodels = submodelRepoClient.get_all_submodels().result
# print(all_submodels)
#
# # modify a submodel
# test_submodel = all_submodels[0]
# test_submodel.id_short = "Test123"
# submodelRepoClient.put_submodel_by_id(test_submodel, string_to_base64url(test_submodel.id))
#
# # delete a submodel
# submodelRepoClient.delete_submodel_by_id(string_to_base64url(test_submodel.id))
#
# # create a new submodel
# new_submodel = model.Submodel("https://acplt.org/TestSubmodel")
# submodelRepoClient.post_submodel(new_submodel)

