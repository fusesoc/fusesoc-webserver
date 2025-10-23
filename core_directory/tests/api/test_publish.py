import pytest

from io import BytesIO

from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage

from core_directory.models import Vendor, Library, Project, CorePackage

import pathlib

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"

@pytest.fixture(autouse=True)
def patch_corepackage_storage(settings):
    from ...storages.dummy_storage import DummyStorage
    settings.DEFAULT_FILE_STORAGE = 'path.to.dummy_storage.DummyStorage'
    CorePackage._meta.get_field('core_file').storage = DummyStorage()
    CorePackage._meta.get_field('signature_file').storage = DummyStorage()
    
def get_core_sig_pairs(directory):
    for core_file in directory.glob("*.core"):
        sig_file = core_file.with_suffix(".sig")
        yield (core_file, sig_file if sig_file.exists() else None)

# Precompute pairs and ids for valid and invalid
valid_pairs = list(get_core_sig_pairs(FIXTURES / "valid"))
valid_ids = [f"valid/{core_path.name}" for core_path, _ in valid_pairs]

invalid_pairs = list(get_core_sig_pairs(FIXTURES / "invalid"))
invalid_ids = [f"invalid/{core_path.name}" for core_path, _ in invalid_pairs]

@pytest.mark.django_db
def test_publish_no_core_file(client, mocker):
    url = reverse('core_directory:publish')
    mock_save = mocker.patch('django.core.files.storage.default_storage.save', return_value='test_core.core')
    
    response = client.post(url, data={})
    data = response.json()
    assert response.status_code == 400
    assert "error" in data
    mock_save.assert_not_called()

@pytest.mark.django_db
@pytest.mark.parametrize(
    "core_path,sig_path",
    valid_pairs,
    ids=valid_ids
)
def test_publish_valid_core_and_sig(client, mocker, core_path, sig_path):
    url = reverse('core_directory:publish')

    # Get the DummyStorage instance used by the FileFields
    storage_core = CorePackage._meta.get_field('core_file').storage
    storage_sig = CorePackage._meta.get_field('signature_file').storage
    # Patch the save method on DummyStorage
    mock_save_core = mocker.patch.object(storage_core, 'save', side_effect=lambda name, content, **kwargs: name)
    mock_save_sig = mocker.patch.object(storage_sig, 'save', side_effect=lambda name, content, **kwargs: name)
    
    with open(core_path, "rb") as f_core:
        files = {'core_file': SimpleUploadedFile(core_path.name, f_core.read(), content_type="application/x-yaml")}
        if sig_path:
            with open(sig_path, "rb") as f_sig:
                files['signature_file'] = SimpleUploadedFile(sig_path.name, f_sig.read(), content_type="application/x-yaml")
        response = client.post(url, data=files)

    data = response.json()
    assert response.status_code == 201
    assert "message" in data
    assert "Core published successfully" in data["message"]
    mock_save_core.assert_called_once()
    mock_save_sig.assert_called_once()

@pytest.mark.django_db
@pytest.mark.parametrize(
    "core_path,sig_path",
    invalid_pairs,
    ids=invalid_ids
)
def test_publish_invalid_core_and_sig(client, mocker, core_path, sig_path):
    url = reverse('core_directory:publish')
    mock_save = mocker.patch('django.core.files.storage.default_storage.save', return_value='test_core.core')
    
    with open(core_path, "rb") as f_core:
        files = {'core_file': SimpleUploadedFile(core_path.name, f_core.read(), content_type="application/x-yaml")}
        if sig_path:
            with open(sig_path, "rb") as f_sig:
                files['signature_file'] = SimpleUploadedFile(sig_path.name, f_sig.read(), content_type="application/x-yaml")
        response = client.post(url, data=files)
    assert response.status_code == 400
    mock_save.assert_not_called()

@pytest.mark.django_db
@pytest.mark.parametrize(
    "core_path",
    list((FIXTURES / "valid_no_sig").glob("*.core")),
    ids=lambda p: f"valid_no_sig/{p.name}"
)
def test_publish_valid_core_no_sig(client, mocker, core_path):
    url = reverse('core_directory:publish')
    
    # Get the DummyStorage instance used by the FileFields
    storage = CorePackage._meta.get_field('core_file').storage
    # Patch the save method on DummyStorage
    mock_save = mocker.patch.object(storage, 'save', side_effect=lambda name, content, **kwargs: name)

    
    with open(core_path, "rb") as f_core:
        files = {'core_file': SimpleUploadedFile(core_path.name, f_core.read(), content_type="application/x-yaml")}
        response = client.post(url, data=files)
    data = response.json()
    assert response.status_code == 201
    assert "message" in data
    assert "Core published successfully" in data["message"]
    mock_save.assert_called_once()

@pytest.mark.django_db
@pytest.mark.parametrize(
    "core_path",
    list((FIXTURES / "invalid_no_sig").glob("*.core")),
    ids=lambda p: f"invalid_no_sig/{p.name}"
)
def test_publish_invalid_core_no_sig(client, mocker, core_path):
    url = reverse('core_directory:publish')
    
    # Get the DummyStorage instance used by the FileFields
    storage_core = CorePackage._meta.get_field('core_file').storage
    # Patch the save method on DummyStorage
    mock_save_core = mocker.patch.object(storage_core, 'save', side_effect=lambda name, content, **kwargs: name)
    
    with open(core_path, "rb") as f_core:
        files = {'core_file': SimpleUploadedFile(core_path.name, f_core.read(), content_type="application/x-yaml")}
        response = client.post(url, data=files)
    assert response.status_code == 400
    mock_save_core.assert_not_called()

@pytest.mark.django_db
def test_republish_existing_core(client, mocker):
    url = reverse('core_directory:publish')
    
    core_file_content = (
                            'CAPI=2:\n'
                            'name: vendor:library:core:1.0.0\n'
                            'description: "A valid core file for testing with signature."\n'
                            'provider:\n'
                            '   name: github\n'
                            '   user: myuser\n'
                            '   repo: myrepo\n'
                            '   version: "v1.0.0"\n'
                        ).encode('utf-8')

    mock_save = mocker.patch('django.core.files.storage.default_storage.save', return_value='test_core.core')
    mocker.patch('django.core.files.storage.default_storage.exists', side_effect=[False, True])
 
    files = {'core_file': SimpleUploadedFile("test_core.core", core_file_content, content_type="application/x-yaml")}

    response = client.post(url, data=files)
    data = response.json()
    
    assert response.status_code == 201
    assert "message" in data
    assert "Core published successfully" in data["message"]

    files = {'core_file': SimpleUploadedFile("test_core.core", core_file_content, content_type="application/x-yaml")}
    response = client.post(url, data=files)
    
    data = response.json()
    
    assert response.status_code == 409
    assert "error" in data
    assert "already exists" in data["error"]
    mock_save.assert_not_called()
    