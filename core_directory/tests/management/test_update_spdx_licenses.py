import io
import os
from unittest import mock
import pytest

from django.core.management import call_command
from django.conf import settings

# Path to the management command module
COMMAND_PATH = "core_directory.management.commands.update_spdx_licenses"

@pytest.fixture
def dummy_licenses_json():
    # Minimal valid SPDX licenses.json content
    return b'{"licenses": [{"licenseId": "MIT", "seeAlso": ["https://opensource.org/licenses/MIT"]}]}'

@mock.patch(f"{COMMAND_PATH}.requests.get")
def test_command_downloads_and_writes_file(mock_get, tmp_path, dummy_licenses_json):
    # Setup mock response
    mock_response = mock.Mock()
    mock_response.content = dummy_licenses_json
    mock_response.raise_for_status = mock.Mock()
    mock_get.return_value = mock_response

    # Patch settings to use a temp file
    dest_path = tmp_path / "licenses.json"
    with mock.patch.object(settings, "SPDX_LICENSES_PATH", str(dest_path)):
        out = io.StringIO()
        call_command("update_spdx_licenses", stdout=out)
        # Check output
        assert "Downloading SPDX license list" in out.getvalue()
        assert "SPDX license list updated at" in out.getvalue()
        # Check file written
        assert dest_path.exists()
        assert dest_path.read_bytes() == dummy_licenses_json

@mock.patch(f"{COMMAND_PATH}.requests.get")
def test_command_creates_directory_if_missing(mock_get, tmp_path, dummy_licenses_json):
    # Setup mock response
    mock_response = mock.Mock()
    mock_response.content = dummy_licenses_json
    mock_response.raise_for_status = mock.Mock()
    mock_get.return_value = mock_response

    # Use a nested directory that doesn't exist yet
    dest_dir = tmp_path / "nested" / "spdx"
    dest_path = dest_dir / "licenses.json"
    with mock.patch.object(settings, "SPDX_LICENSES_PATH", str(dest_path)):
        out = io.StringIO()
        call_command("update_spdx_licenses", stdout=out)
        assert dest_path.exists()
        assert dest_path.read_bytes() == dummy_licenses_json

@mock.patch(f"{COMMAND_PATH}.requests.get")
def test_command_handles_http_error(mock_get, tmp_path):
    # Simulate HTTP error
    mock_response = mock.Mock()
    mock_response.raise_for_status.side_effect = Exception("HTTP error")
    mock_get.return_value = mock_response

    dest_path = tmp_path / "licenses.json"
    with mock.patch.object(settings, "SPDX_LICENSES_PATH", str(dest_path)):
        out = io.StringIO()
        with pytest.raises(Exception):
            call_command("update_spdx_licenses", stdout=out)
        # File should not exist
        assert not dest_path.exists()

@mock.patch(f"{COMMAND_PATH}.requests.get")
def test_command_uses_timeout(mock_get, tmp_path, dummy_licenses_json):
    # Setup mock response
    mock_response = mock.Mock()
    mock_response.content = dummy_licenses_json
    mock_response.raise_for_status = mock.Mock()
    mock_get.return_value = mock_response

    dest_path = tmp_path / "licenses.json"
    with mock.patch.object(settings, "SPDX_LICENSES_PATH", str(dest_path)):
        out = io.StringIO()
        call_command("update_spdx_licenses", stdout=out)
        # Check that timeout was set in requests.get
        assert mock_get.call_args[1]["timeout"] == 10