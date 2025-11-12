import pytest
import io
import zipfile
from django.urls import reverse
from core_directory.models import Vendor, Library, Project, CorePackage

@pytest.fixture(autouse=True)
def patch_corepackage_storage(settings):
    from ...storages.dummy_storage import DummyStorage
    settings.DEFAULT_FILE_STORAGE = 'path.to.dummy_storage.DummyStorage'
    CorePackage._meta.get_field('core_file').storage = DummyStorage()
    CorePackage._meta.get_field('signature_file').storage = DummyStorage()

@pytest.mark.django_db
def test_getarchive_success_core_and_signature(client, mocker):
    # Set up test data: one core with signature, one without
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    project1 = Project.objects.create(vendor=vendor, library=library, name="foo", description="desc")
    project2 = Project.objects.create(vendor=vendor, library=library, name="bar", description="desc")

    cp1 = CorePackage.objects.create(
        project=project1,
        vlnv_name="acme:lib1:foo:1.0.0",
        version="1.0.0",
        version_major=1,
        version_minor=0,
        version_patch=0,
        core_file="foo.core",
        signature_file="foo.sig",
        description="desc"
    )
    cp2 = CorePackage.objects.create(
        project=project2,
        vlnv_name="acme:lib1:bar:1.0.0",
        version="1.0.0",
        version_major=1,
        version_minor=0,
        version_patch=0,
        core_file="bar.core",
        signature_file=None,
        description="desc"
    )

    # Patch the storage for both core and signature files
    core_storage = CorePackage._meta.get_field('core_file').storage
    sig_storage = CorePackage._meta.get_field('signature_file').storage

    def fake_core_open(name, mode='rb'):
        if name == cp1.core_file.name:
            return io.BytesIO(b"foo core content")
        elif name == cp2.core_file.name:
            return io.BytesIO(b"bar core content")
        raise FileNotFoundError(name)

    def fake_sig_open(name, mode='rb'):
        if cp1.signature_file and name == cp1.signature_file.name:
            return io.BytesIO(b"foo signature content")
        raise FileNotFoundError(name)

    mocker.patch.object(core_storage, 'open', side_effect=fake_core_open)
    mocker.patch.object(sig_storage, 'open', side_effect=fake_sig_open)

    url = reverse('core_directory:archive_get')
    response = client.get(url)
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/zip'
    assert response['Content-Disposition'].endswith('fusesoc_pd_archive.zip"')

    # Check the contents of the zip archive
    with io.BytesIO(response.content) as zip_bytes:
        with zipfile.ZipFile(zip_bytes, 'r') as archive:
            namelist = archive.namelist()
            assert cp1.sanitized_vlnv + ".core" in namelist
            assert cp1.sanitized_vlnv + ".core.sig" in namelist
            assert cp2.sanitized_vlnv + ".core" in namelist
            assert archive.read(cp1.sanitized_vlnv + ".core") == b"foo core content"
            assert archive.read(cp1.sanitized_vlnv + ".core.sig") == b"foo signature content"
            assert archive.read(cp2.sanitized_vlnv + ".core") == b"bar core content"

@pytest.mark.django_db
def test_getarchive_core_file_missing(client, mocker):
    # Set up test data: one core, but file is missing in storage
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    project = Project.objects.create(vendor=vendor, library=library, name="foo", description="desc")
    cp = CorePackage.objects.create(
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
    mocker.patch.object(core_storage, 'open', side_effect=FileNotFoundError("not found"))

    url = reverse('core_directory:archive_get')
    response = client.get(url)
    assert response.status_code == 500
    assert b"Error retrieving archive" in response.content

@pytest.mark.django_db
def test_getarchive_signature_file_missing(client, mocker):
    # Set up test data: core with signature, but signature file missing
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    project = Project.objects.create(vendor=vendor, library=library, name="foo", description="desc")
    cp = CorePackage.objects.create(
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

    mocker.patch.object(core_storage, 'open', return_value=io.BytesIO(b"foo core content"))
    mocker.patch.object(sig_storage, 'open', side_effect=FileNotFoundError("not found"))

    url = reverse('core_directory:archive_get')
    response = client.get(url)
    assert response.status_code == 500
    assert b"Error retrieving archive" in response.content
            