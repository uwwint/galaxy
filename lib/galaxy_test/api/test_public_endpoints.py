from urllib.parse import urljoin
from uuid import uuid4

import requests

from galaxy_test.base.api_asserts import (
    assert_has_keys,
    assert_not_has_keys,
)
from .test_configuration import (
    TEST_KEYS_FOR_ADMIN_ONLY,
    TEST_KEYS_FOR_ALL_USERS,
)


def test_public_api_reads_are_accessible_without_auth(anonymous_galaxy_interactor, api_test_config_object):
    version = anonymous_galaxy_interactor._get("version")
    assert version.status_code == 200
    version_json = version.json()
    assert_has_keys(version_json, "version_major", "version_minor")

    configuration = anonymous_galaxy_interactor._get("configuration")
    assert configuration.status_code == 200
    configuration_json = configuration.json()
    assert_has_keys(configuration_json, *TEST_KEYS_FOR_ALL_USERS)
    assert_not_has_keys(configuration_json, *TEST_KEYS_FOR_ADMIN_ONLY)

    tours = anonymous_galaxy_interactor._get("tours")
    assert tours.status_code == 200
    tours_json = tours.json()
    assert isinstance(tours_json, list)
    assert any(tour["id"] == "core.history" for tour in tours_json)

    datatypes = anonymous_galaxy_interactor._get("datatypes")
    assert datatypes.status_code == 200
    datatypes_json = datatypes.json()
    assert isinstance(datatypes_json, list)
    assert "tabular" in datatypes_json
    assert "fasta" in datatypes_json

    display_applications = anonymous_galaxy_interactor._get("display_applications")
    assert display_applications.status_code == 200
    display_applications_json = display_applications.json()
    assert isinstance(display_applications_json, list)
    assert display_applications_json
    assert_has_keys(display_applications_json[0], "id", "name", "version", "filename_", "links")

    licenses = anonymous_galaxy_interactor._get("licenses")
    assert licenses.status_code == 200
    licenses_json = licenses.json()
    assert isinstance(licenses_json, list)
    assert licenses_json
    assert_has_keys(licenses_json[0], "licenseId")

    dynamic_tools = anonymous_galaxy_interactor._get("dynamic_tools")
    assert dynamic_tools.status_code == 200
    assert isinstance(dynamic_tools.json(), list)

    unprivileged_tools = anonymous_galaxy_interactor._get("unprivileged_tools")
    assert unprivileged_tools.status_code == 200
    assert isinstance(unprivileged_tools.json(), list)

    short_term_storage = anonymous_galaxy_interactor._get(f"short_term_storage/{uuid4()}")
    assert short_term_storage.status_code == 404

    context = requests.get(urljoin(api_test_config_object.url, "context"))
    assert context.status_code == 200
    context_json = context.json()
    assert_has_keys(context_json, "config", "user")
    assert isinstance(context_json["user"], dict)
    assert context_json["user"]["id"] is None

    discovery = requests.get(urljoin(api_test_config_object.url, ".well-known/oauth-authorization-server"))
    assert discovery.status_code == 200
    discovery_json = discovery.json()
    assert_has_keys(discovery_json, "issuer", "jwks_uri")

    jwks = requests.get(urljoin(api_test_config_object.url, ".well-known/jwks.json"))
    assert jwks.status_code == 200
    jwks_json = jwks.json()
    assert_has_keys(jwks_json, "keys")
    assert isinstance(jwks_json["keys"], list)


def test_ga4gh_service_info_is_public(api_test_config_object):
    drs_service_info = requests.get(urljoin(api_test_config_object.url, "ga4gh/drs/v1/service-info"))
    assert drs_service_info.status_code == 200
    assert_has_keys(drs_service_info.json(), "id", "name", "type", "version")

    wes_service_info = requests.get(urljoin(api_test_config_object.url, "ga4gh/wes/v1/service-info"))
    assert wes_service_info.status_code == 200
    assert_has_keys(wes_service_info.json(), "id", "name", "type", "version")
