import pytest
import io
from django.urls import reverse

from django.core.files.storage import default_storage, FileSystemStorage
from core_directory.models import Vendor, Library, Project, CorePackage


@pytest.fixture(autouse=True)
def patch_corepackage_storage(settings):
    from ...storages.dummy_storage import DummyStorage
    settings.DEFAULT_FILE_STORAGE = 'path.to.dummy_storage.DummyStorage'
    CorePackage._meta.get_field('core_file').storage = DummyStorage()
    CorePackage._meta.get_field('signature_file').storage = DummyStorage()

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
        core_file="foo.core",
        description="desc"
    )
    # Patch the storage used by the FileField
    storage = CorePackage._meta.get_field('core_file').storage
    mocker.patch.object(storage, 'open', return_value=io.BytesIO(b"core file content"))

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
    mocker.patch.object(default_storage, 'open', side_effect=FileNotFoundError("No such file"))
    CorePackage.objects.create(
        project=project,
        vlnv_name="acme:lib1:foo:1.0.0",
        version="1.0.0",
        version_major=1,
        version_minor=0,
        version_patch=0,
        core_file="foo.core",
        description="desc"
    )

    storage = CorePackage._meta.get_field('core_file').storage
    mocker.patch.object(storage, 'open', side_effect=FileNotFoundError("No such file"))

    url = reverse('core_directory:core_get')
    response = client.get(url, {"core": "acme:lib1:foo:1.0.0"})
    assert response.status_code == 404
    assert b"not available" in response.content or b"not available" in response.json().get("error", "").lower()

@pytest.mark.django_db
def test_getcore_missing_param(client):
    url = reverse("core_directory:core_get")
    response = client.get(url)
    assert response.status_code == 400
    assert b"missing" in response.content or b"required" in response.content
import pytest
import io
from django.urls import reverse
from core_directory.models import Vendor, Library, Project, CorePackage

@pytest.mark.django_db
@pytest.mark.django_db
def test_getcore_signature_success(client, mocker):
    # Set up test data with both core and signature files
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
        core_file="foo.core",
        signature_file="foo.sig",
        description="desc"
    )
    core_storage = CorePackage._meta.get_field('core_file').storage
    sig_storage = CorePackage._meta.get_field('signature_file').storage

    mocker.patch.object(core_storage, 'open', side_effect=lambda *a, **kw: io.BytesIO(b"core file content"))
    mocker.patch.object(sig_storage, 'open', side_effect=lambda *a, **kw: io.BytesIO(b"signature file content"))

    url = reverse('core_directory:core_get')
    response = client.get(url, {"core": "acme:lib1:foo:1.0.0"})
    assert response.status_code == 200
    assert b'core file content' in response.content
    assert response["Content-Disposition"].endswith("acme_lib1_foo_1.0.0.core")

    # Test signature file download (assuming your API supports a param like ?sig=1)
    response = client.get(url, {"core": "acme:lib1:foo:1.0.0", "signature": "1"})
    assert response.status_code == 200
    assert b'signature file content' in response.content
    assert response["Content-Disposition"].endswith("acme_lib1_foo_1.0.0.core.sig")

@pytest.mark.django_db
def test_getcore_signature_not_found(client, mocker):
    # Set up test data with only core file, no signature file
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
        core_file="foo.core",
        signature_file=None,
        description="desc"
    )
    core_storage = CorePackage._meta.get_field('core_file').storage
    sig_storage = CorePackage._meta.get_field('signature_file').storage
    mocker.patch.object(core_storage, 'open', return_value=io.BytesIO(b"core file content"))
    # Simulate signature file not found
    mocker.patch.object(sig_storage, 'open', side_effect=FileNotFoundError("No such file"))

    url = reverse('core_directory:core_get')
    # Try to get signature file (assuming ?sig=1 triggers signature download)
    response = client.get(url, {"core": "acme:lib1:foo:1.0.0", "signature": "1"})
    assert response.status_code == 404
    assert b"not found" in response.content or b"not found" in response.json().get("error", "").lower()
