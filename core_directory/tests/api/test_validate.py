import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
import pathlib

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"

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
def test_validate_no_core_file(client):
    url = reverse('core_directory:validate')
    response = client.post(url, data={})
    data = response.json()
    assert response.status_code == 400
    assert "error" in data
    assert "No file provided" in data["error"]

@pytest.mark.django_db
@pytest.mark.parametrize(
    "core_path,sig_path",
    valid_pairs,
    ids=valid_ids
)
def test_validate_valid_core_and_sig(client, core_path, sig_path):
    url = reverse('core_directory:validate')
    with open(core_path, "rb") as f_core:
        files = {'core_file': SimpleUploadedFile(core_path.name, f_core.read(), content_type="application/x-yaml")}
        if sig_path:
            with open(sig_path, "rb") as f_sig:
                files['signature_file'] = SimpleUploadedFile(sig_path.name, f_sig.read(), content_type="application/x-yaml")
        response = client.post(url, data=files)

    data = response.json()
    assert response.status_code == 200
    assert "message" in data
    assert "Core file is valid" in data["message"]

@pytest.mark.django_db
@pytest.mark.parametrize(
    "core_path,sig_path",
    invalid_pairs,
    ids=invalid_ids
)
def test_validate_invalid_core_and_sig(client, core_path, sig_path):
    url = reverse('core_directory:validate')
    with open(core_path, "rb") as f_core:
        files = {'core_file': SimpleUploadedFile(core_path.name, f_core.read(), content_type="application/x-yaml")}
        if sig_path:
            with open(sig_path, "rb") as f_sig:
                files['signature_file'] = SimpleUploadedFile(sig_path.name, f_sig.read(), content_type="application/x-yaml")
        response = client.post(url, data=files)
    assert response.status_code == 400

@pytest.mark.django_db
@pytest.mark.parametrize(
    "core_path",
    list((FIXTURES / "valid_no_sig").glob("*.core")),
    ids=lambda p: f"valid_no_sig/{p.name}"
)
def test_validate_valid_core_no_sig(client, core_path):
    url = reverse('core_directory:validate')
    with open(core_path, "rb") as f_core:
        files = {'core_file': SimpleUploadedFile(core_path.name, f_core.read(), content_type="application/x-yaml")}
        response = client.post(url, data=files)
    data = response.json()
    assert response.status_code == 200
    assert "message" in data
    assert "Core file is valid" in data["message"]

@pytest.mark.django_db
@pytest.mark.parametrize(
    "core_path",
    list((FIXTURES / "invalid_no_sig").glob("*.core")),
    ids=lambda p: f"invalid_no_sig/{p.name}"
)
def test_validate_invalid_core_no_sig(client, core_path):
    url = reverse('core_directory:validate')
    with open(core_path, "rb") as f_core:
        files = {'core_file': SimpleUploadedFile(core_path.name, f_core.read(), content_type="application/x-yaml")}
        response = client.post(url, data=files)
    assert response.status_code == 400
