import pytest
from django.urls import reverse
from core_directory.models import Vendor, Library, Project, CorePackage

@pytest.mark.django_db
def test_getcore_success(client, mocker):
    # Set up test data
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    project = Project.objects.create(vendor=vendor, library=library, name="foo", description="desc")
    core_package = CorePackage.objects.create(
        project=project,
        vlnv_name="acme:lib1:foo:1.0.0",
        version="1.0.0",
        version_major=1,
        version_minor=0,
        version_patch=0,
        core_url="https://example.com/foo.core",
        description="desc"
    )

    # Mock requests.get to return a fake file
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.content = b"core file content"
    mocker.patch("requests.get", return_value=mock_response)

    url = reverse('core_directory:core_get')
    response = client.get(url, {"core": "acme:lib1:foo:1.0.0"})
    assert response.status_code == 200
    assert b'core file content' in response.content
    assert response["Content-Disposition"].endswith("acme_lib1_foo_1.0.0.core")

@pytest.mark.django_db
def test_getcore_not_found(client):
    url = reverse('core_directory:core_get')
    response = client.get(url, {"core": "acme:lib1:doesnotexist:1.0.0"})
    assert response.status_code == 404
    assert b"not available" in response.content or b"not available" in response.json().get("error", "").lower()

import pytest
from django.urls import reverse
from core_directory.models import Vendor, Library, Project, CorePackage

@pytest.mark.django_db
def test_getcore_file_not_found(client, mocker):
    # Set up test data: core exists in DB
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    project = Project.objects.create(vendor=vendor, library=library, name="foo", description="desc")
    core_package = CorePackage.objects.create(
        project=project,
        vlnv_name="acme:lib1:foo:1.0.0",
        version="1.0.0",
        version_major=1,
        version_minor=0,
        version_patch=0,
        core_url="https://example.com/foo.core",
        description="desc"
    )

    # Mock requests.get to simulate file not found (404)
    mock_response = mocker.Mock()
    mock_response.status_code = 404
    mock_response.content = b""
    mocker.patch("requests.get", return_value=mock_response)

    url = reverse('core_directory:core_get')
    response = client.get(url, {"core": "acme:lib1:foo:1.0.0"})
    assert response.status_code == 404
    assert b"not found" in response.content or b"not found" in response.json().get("error", "").lower()

@pytest.mark.django_db
def test_getcore_missing_param(client):
    url = reverse("core_directory:core_get")
    response = client.get(url)
    assert response.status_code == 400
    assert b"missing" in response.content or b"required" in response.content