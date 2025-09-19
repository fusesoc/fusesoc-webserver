import pytest
import json
from unittest import mock
from django.core.exceptions import ValidationError

# Patch settings for SPDX_LICENSES_PATH
@pytest.fixture
def spdx_settings(tmp_path, monkeypatch):
    licenses_json = tmp_path / "licenses.json"
    monkeypatch.setattr("django.conf.settings.SPDX_LICENSES_PATH", str(licenses_json))
    return licenses_json

# Minimal SPDX licenses.json content for testing
MINIMAL_LICENSES_JSON = {
    "licenses": [
        {
            "licenseId": "MIT",
            "seeAlso": ["https://opensource.org/licenses/MIT"],
            "reference": "https://spdx.org/licenses/MIT.html"
        },
        {
            "licenseId": "BSD-2-Clause",
            "seeAlso": ["https://opensource.org/licenses/BSD-2-Clause"],
            "reference": "https://spdx.org/licenses/BSD-2-Clause.html"
        }
    ]
}

def write_licenses_json(path, content=MINIMAL_LICENSES_JSON):
    path.write_text(json.dumps(content), encoding="utf-8")

def test_get_spdx_license_ids_and_choices(spdx_settings):
    from utils import spdx
    write_licenses_json(spdx_settings)
    # Clear cache in case of previous test runs
    spdx._load_spdx_license_data.cache_clear()
    ids = spdx.get_spdx_license_ids()
    assert "MIT" in ids
    assert "BSD-2-Clause" in ids
    choices = spdx.get_spdx_choices()
    assert ("MIT", "MIT") in choices
    assert ("BSD-2-Clause", "BSD-2-Clause") in choices

def test_get_spdx_license_url(spdx_settings):
    from utils import spdx
    write_licenses_json(spdx_settings)
    spdx._load_spdx_license_data.cache_clear()
    url = spdx.get_spdx_license_url("MIT")
    assert url == "https://opensource.org/licenses/MIT"
    url2 = spdx.get_spdx_license_url("BSD-2-Clause")
    assert url2 == "https://opensource.org/licenses/BSD-2-Clause"
    url3 = spdx.get_spdx_license_url("NOT_A_LICENSE")
    assert url3 is None

def test_validate_spdx_valid_and_invalid(spdx_settings):
    from utils import spdx
    write_licenses_json(spdx_settings)
    spdx._load_spdx_license_data.cache_clear()
    # Valid
    spdx.validate_spdx("MIT")
    spdx.validate_spdx("BSD-2-Clause")
    # Invalid
    with pytest.raises(ValidationError):
        spdx.validate_spdx("NOT_A_LICENSE")

def test_load_spdx_license_data_file_not_found(monkeypatch):
    from utils import spdx
    # Point to a non-existent file
    monkeypatch.setattr("django.conf.settings.SPDX_LICENSES_PATH", "/tmp/does_not_exist.json")
    spdx._load_spdx_license_data.cache_clear()
    assert spdx.get_spdx_license_ids() == set()
    assert spdx.get_spdx_choices() == []
    assert spdx.get_spdx_license_url("MIT") is None

def test_load_spdx_license_data_json_error(tmp_path, monkeypatch):
    from utils import spdx
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr("django.conf.settings.SPDX_LICENSES_PATH", str(bad_json))
    spdx._load_spdx_license_data.cache_clear()
    assert spdx.get_spdx_license_ids() == set()
    assert spdx.get_spdx_choices() == []
    assert spdx.get_spdx_license_url("MIT") is None
