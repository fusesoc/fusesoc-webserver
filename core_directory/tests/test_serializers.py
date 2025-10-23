import io
import pytest

from unittest import mock

import yaml
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from jsonschema import ValidationError as JsonSchemaValidationError, SchemaError
import json

from core_directory.serializers import CoreSerializer
from core_directory.models import Vendor, Library, Project, CorePackage
from utils.spdx import get_spdx_license_ids

@pytest.fixture(autouse=True)
def patch_corepackage_storage(settings):
    from ..storages.dummy_storage import DummyStorage
    settings.DEFAULT_FILE_STORAGE = 'path.to.dummy_storage.DummyStorage'
    CorePackage._meta.get_field('core_file').storage = DummyStorage()
    CorePackage._meta.get_field('signature_file').storage = DummyStorage()

# --- Helper to create a fake file object ---
class FakeFile(io.BytesIO):
    def __init__(self, content, name="test.core", size=None):
        super().__init__(content)
        self.name = name
        self.size = size if size is not None else len(content)

# --- Test: core_file extension and size ---
def test_validate_core_file_extension_and_size():
    s = CoreSerializer()
    # Invalid extension
    with pytest.raises(ValidationError):
        s.validate_core_file(FakeFile(b"dummy", name="bad.txt"))
    # Too large
    with pytest.raises(ValidationError):
        s.validate_core_file(FakeFile(b"x" * (65 * 1024), name="test.core"))
    # Valid
    assert s.validate_core_file(FakeFile(b"dummy", name="test.core"))

# --- Test: signature_file extension and size ---
def test_validate_signature_file_extension_and_size():
    s = CoreSerializer()
    # Invalid extension
    with pytest.raises(ValidationError):
        s.validate_signature_file(FakeFile(b"dummy", name="bad.txt"))
    # Too large
    with pytest.raises(ValidationError):
        s.validate_signature_file(FakeFile(b"x" * (11 * 1024), name="test.sig"))
    # Valid
    assert s.validate_signature_file(FakeFile(b"dummy", name="test.sig"))

# --- Test: core_file missing CAPI=2 header ---
def test_validate_missing_capi_header(tmp_path):
    s = CoreSerializer()
    core_file = FakeFile(b"notcapi\nname: vendor:lib:core:1.0.0\n", name="test.core")
    attrs = {"core_file": core_file}
    with pytest.raises(ValidationError) as excinfo:
        s.validate(attrs)
    assert "Core file does not start with \"CAPI=2:\"" in str(excinfo.value)

# --- Test: valid core file, valid signature file, matching names ---
@pytest.mark.django_db
@mock.patch("core_directory.serializers.Core2Parser")
@mock.patch("core_directory.serializers.CoreSerializer._validate_against_schema")
def test_validate_valid_core_and_signature(mock_schema, mock_parser, tmp_path):
    s = CoreSerializer()
    # Minimal valid core YAML
    core_yaml = b"CAPI=2:\nname: vendor:lib:core:1.0.0\n"
    sig_yaml = b"coresig:\n  name: vendor:lib:core:1.0.0\n  signatures: []\n"
    core_file = FakeFile(core_yaml, name="test.core")
    sig_file = FakeFile(sig_yaml, name="test.sig")
    attrs = {"core_file": core_file, "signature_file": sig_file}
    # Patch YAML loader to return dicts
    with mock.patch("core_directory.serializers.yaml.safe_load", side_effect=[
        {"CAPI=2": None, "name": "vendor:lib:core:1.0.0"},
        {"coresig": {"name": "vendor:lib:core:1.0.0", "signatures": []}}
    ]):
        result = s.validate(attrs)
        assert result["vlnv_name"] == "vendor:lib:core:1.0.0"
        assert result["vendor_name"] == "vendor"
        assert result["library_name"] == "lib"
        assert result["project_name"] == "core"
        assert result["version"] == "1.0.0"

# --- Test: signature file with mismatched name ---
@mock.patch("core_directory.serializers.Core2Parser")
@mock.patch("core_directory.serializers.CoreSerializer._validate_against_schema")
def test_validate_signature_mismatch(mock_schema, mock_parser, tmp_path):
    s = CoreSerializer()
    core_yaml = b"CAPI=2:\nname: vendor:lib:core:1.0.0\n"
    sig_yaml = b"coresig:\n  name: vendor:lib:othercore:1.0.0\n  signatures: []\n"
    core_file = FakeFile(core_yaml, name="test.core")
    sig_file = FakeFile(sig_yaml, name="test.sig")
    attrs = {"core_file": core_file, "signature_file": sig_file}
    with mock.patch("core_directory.serializers.yaml.safe_load", side_effect=[
        {"CAPI=2": None, "name": "vendor:lib:core:1.0.0"},
        {"coresig": {"name": "vendor:lib:othercore:1.0.0", "signatures": []}}
    ]):
        with pytest.raises(ValidationError) as excinfo:
            s.validate(attrs)
        assert "Signature file not valid for vendor:lib:core:1.0.0" in str(excinfo.value)

# --- Test: valid SPDX license string is accepted ---
@pytest.mark.django_db
def test_validate_license_valid_spdx_string():
    s = CoreSerializer()
    valid_license = next(iter(get_spdx_license_ids()))
    core_file = FakeFile(
        b"CAPI=2:\nname: vendor:lib:core:1.0.0\ndescription: Test core\nlicense: %s\n" % valid_license.encode(),
        name="test.core"
    )
    attrs = {"core_file": core_file}
    with mock.patch("core_directory.serializers.yaml.safe_load", return_value={
        "CAPI=2": None,
        "name": "vendor:lib:core:1.0.0",
        "description": "Test core description",
        "license": valid_license,
        "provider": {
            "name": "github",
            "user": "testuser",
            "repo": "testrepo",
            "version": "0123456789abcdef0123456789abcdef01234567"
        }
    }):
        result = s.validate(attrs)
        assert result["spdx_license"] == valid_license

# --- Test: LicenseRef-... is rejected ---
@pytest.mark.django_db
def test_validate_license_ref_rejected():
    s = CoreSerializer()
    core_file = FakeFile(
        b"CAPI=2:\nname: vendor:lib:core:1.0.0\ndescription: Test core\nlicense: LicenseRef-MyCustomLicense\n",
        name="test.core"
    )
    attrs = {"core_file": core_file}
    with mock.patch("core_directory.serializers.yaml.safe_load", return_value={
        "CAPI=2": None,
        "name": "vendor:lib:core:1.0.0",
        "description": "Test core description",
        "license": "LicenseRef-MyCustomLicense",
        "provider": {
            "name": "github",
            "user": "testuser",
            "repo": "testrepo",
            "version": "0123456789abcdef0123456789abcdef01234567"
        }
    }):
        with pytest.raises(ValidationError) as excinfo:
            s.validate(attrs)
        assert "is not a valid SPDX license identifier" in str(excinfo.value)

# --- Test: license object is rejected ---
def test_validate_license_object_rejected():
    s = CoreSerializer()
    core_file = FakeFile(
        b"CAPI=2:\n",
        name="test.core"
    )
    attrs = {"core_file": core_file}
    with mock.patch("core_directory.serializers.yaml.safe_load", return_value={
        "CAPI=2": None,
        "name": "vendor:lib:core:1.0.0",
        "description": "Test core description",
        "license": {"name": "My Custom License", "text": "Full license text"},
        "provider": {
            "name": "github",
            "user": "testuser",
            "repo": "testrepo",
            "version": "0123456789abcdef0123456789abcdef01234567"
        }
    }):
        with pytest.raises(ValidationError) as excinfo:
            s.validate(attrs)
        assert "Custom license objects are not supported" in str(excinfo.value)

# --- Test: missing license is accepted ---
@pytest.mark.django_db
def test_validate_license_missing_ok():
    s = CoreSerializer()
    core_file = FakeFile(
        b"CAPI=2:\n",
        name="test.core"
    )
    attrs = {"core_file": core_file}
    with mock.patch("core_directory.serializers.yaml.safe_load", return_value={
        "CAPI=2": None,
        "name": "vendor:lib:core:1.0.0",
        "description": "Test core description",
        # No license field,
        "provider": {
            "name": "github",
            "user": "testuser",
            "repo": "testrepo",
            "version": "0123456789abcdef0123456789abcdef01234567"
        }
    }):
        result = s.validate(attrs)
        assert result["spdx_license"] is None

# --- Test: YAML error handling ---
def test_validate_yaml_error(tmp_path):
    s = CoreSerializer()
    core_file = FakeFile(b"CAPI=2:\n:bad_yaml", name="test.core")
    attrs = {"core_file": core_file}
    # Patch yaml.safe_load to raise YAMLError
    with mock.patch("core_directory.serializers.yaml.safe_load", side_effect=yaml.YAMLError("bad yaml")):
        with pytest.raises(ValidationError) as excinfo:
            s.validate(attrs)
        assert "Error while parsing file" in str(excinfo.value)

@pytest.mark.django_db
def test_core_serializer_create():
    # Prepare validated_data as expected by create()
    validated_data = {
        "vendor_name": "Acme",
        "library_name": "Lib1",
        "project_name": "Core1",
        "vlnv_name": "Acme:Lib1:Core1:1.0.0",
        "sanitized_name": "acme_lib1_core1_1_0_0",
        "version": "1.0.0",
        "core_file": SimpleUploadedFile("acme_lib1_core1_1_0_0.core", b"CAPI=2:\nname: Acme:Lib1:Core1:1.0.0\n"),
        "signature_file": None,
        "description": "A test core package.",
        "core_content_yaml": {
            "filesets": {
                "fs1": {
                    "files": ["file1.v"],
                    "file_type": "verilogSource"
                }
            },
            "targets": {
                "sim": {
                    "filesets": ["fs1"],
                    "parameters": {"param1": "value"},
                    "default_tool": "icarus",
                    "flow": "simflow",
                    "description": "Simulation target"
                }
            }
        }
    }
    serializer = CoreSerializer()
    instance = serializer.create(validated_data)

    # Check that the CorePackage and related objects were created
    assert isinstance(instance, CorePackage)
    assert instance.project.vendor.name == "Acme"
    assert instance.project.library.name == "Lib1"
    assert instance.project.name == "Core1"
    assert instance.version == "1.0.0"
    assert instance.core_file == "acme_lib1_core1_1_0_0.core"
    assert instance.description == "A test core package."
    # Fileset and Target should also exist
    filesets = instance.filesets.all()
    assert filesets.count() == 1
    assert filesets[0].name == "fs1"
    assert filesets[0].file_type == "verilogSource"
    targets = instance.target_configurations.all()
    assert targets.count() == 1
    assert targets[0].target.name == "sim"
    assert targets[0].default_tool == "icarus"
    assert targets[0].flow == "simflow"
    assert targets[0].description == "Simulation target"
    # Fileset is linked to target
    assert filesets[0] in targets[0].filesets.all()

@pytest.mark.django_db
def test_core_serializer_create_with_dependencies():
    validated_data = {
        "vendor_name": "Acme",
        "library_name": "Lib1",
        "project_name": "Core1",
        "vlnv_name": "Acme:Lib1:Core1:1.0.0",
        "version": "1.0.0",
        "sanitized_name": "acme_lib1_core1_1_0_0",
        "core_file": SimpleUploadedFile("acme_lib1_core1_1_0_0.core", b"CAPI=2:\nname: Acme:Lib1:Core1:1.0.0\n"),
        "sig_url": None,
        "description": "A test core package.",
        "core_content_yaml": {
            "filesets": {
                "fs1": {
                    "files": ["file1.v"],
                    "file_type": "verilogSource",
                    "depend": [
                        "othercore",                # Simple dependency
                        "sim? (conditionalcore)"    # Conditional dependency
                    ]
                }
            },
            "targets": {
                "sim": {
                    "filesets": ["fs1"],
                    "parameters": {"param1": "value"},
                    "default_tool": "icarus",
                    "flow": "simflow",
                    "description": "Simulation target"
                }
            }
        }
    }
    serializer = CoreSerializer()
    instance = serializer.create(validated_data)

    # Check dependencies
    fileset = instance.filesets.get(name="fs1")
    deps = list(fileset.dependencies.all())
    assert len(deps) == 2

    # Check simple dependency
    dep1 = next(d for d in deps if d.dependency_core_name == "othercore")
    assert dep1.dependency_condition is None

    # Check conditional dependency
    dep2 = next(d for d in deps if d.dependency_core_name == "conditionalcore")
    assert dep2.dependency_condition == "sim"

    # Also check the rest of the structure as before
    assert fileset.file_type == "verilogSource"
    targets = instance.target_configurations.all()
    assert targets.count() == 1
    assert fileset in targets[0].filesets.all()

@pytest.mark.django_db
def test_core_serializer_create_with_valid_spdx_license():
    valid_license = next(iter(get_spdx_license_ids()))
    validated_data = {
        "vendor_name": "Acme",
        "library_name": "Lib1",
        "project_name": "Core1",
        "vlnv_name": "Acme:Lib1:Core1:1.0.0",
        "version": "1.0.0",
        "sanitized_name": "acme_lib1_core1_1_0_0",
        "core_file": SimpleUploadedFile("acme_lib1_core1_1_0_0.core", b"CAPI=2:\nname: Acme:Lib1:Core1:1.0.0\n"),
        "sig_url": None,
        "description": "A test core package.",
        "spdx_license": valid_license,
        "core_content_yaml": {
            "filesets": {
                "fs1": {
                    "files": ["file1.v"],
                    "file_type": "verilogSource"
                }
            },
            "targets": {
                "sim": {
                    "filesets": ["fs1"],
                    "parameters": {"param1": "value"},
                    "default_tool": "icarus",
                    "flow": "simflow",
                    "description": "Simulation target"
                }
            }
        }
    }
    
    serializer = CoreSerializer()
    instance = serializer.create(validated_data)
    assert isinstance(instance, CorePackage)
    assert instance.spdx_license == valid_license

@pytest.mark.django_db
def test_core_serializer_create_with_invalid_license_fails():
    validated_data = {
        "vendor_name": "Acme",
        "library_name": "Lib1",
        "project_name": "Core1",
        "vlnv_name": "Acme:Lib1:Core1:1.0.0",
        "version": "1.0.0",
        "sanitized_name": "acme_lib1_core1_1_0_0",
        "core_file": SimpleUploadedFile("acme_lib1_core1_1_0_0.core", b"CAPI=2:\nname: Acme:Lib1:Core1:1.0.0\n"),
        "sig_url": None,
        "description": "A test core package.",
        "spdx_license": "NOT_A_VALID_LICENSE",
        "core_content_yaml": {
            "filesets": {
                "fs1": {
                    "files": ["file1.v"],
                    "file_type": "verilogSource"
                }
            },
            "targets": {
                "sim": {
                    "filesets": ["fs1"],
                    "parameters": {"param1": "value"},
                    "default_tool": "icarus",
                    "flow": "simflow",
                    "description": "Simulation target"
                }
            }
        }
    }
    
    serializer = CoreSerializer()
    with pytest.raises(Exception):  # Could be ValidationError or IntegrityError depending on your model
        serializer.create(validated_data)

@pytest.mark.django_db
def test_core_serializer_create_with_license_ref_fails():
    validated_data = {
        "vendor_name": "Acme",
        "library_name": "Lib1",
        "project_name": "Core1",
        "vlnv_name": "Acme:Lib1:Core1:1.0.0",
        "version": "1.0.0",
        "core_url": "https://example.com/core",
        "sig_url": None,
        "description": "A test core package.",
        "spdx_license": "LicenseRef-MyCustomLicense",
        "core_content_yaml": {
            "filesets": {
                "fs1": {
                    "files": ["file1.v"],
                    "file_type": "verilogSource"
                }
            },
            "targets": {
                "sim": {
                    "filesets": ["fs1"],
                    "parameters": {"param1": "value"},
                    "default_tool": "icarus",
                    "flow": "simflow",
                    "description": "Simulation target"
                }
            }
        }
    }
    
    serializer = CoreSerializer()
    with pytest.raises(Exception):  # Could be ValidationError or IntegrityError depending on your model
        serializer.create(validated_data)

@pytest.mark.django_db
def test_core_serializer_create_with_missing_license():
    validated_data = {
        "vendor_name": "Acme",
        "library_name": "Lib1",
        "project_name": "Core1",
        "vlnv_name": "Acme:Lib1:Core1:1.0.0",
        "version": "1.0.0",
        "sanitized_name": "acme_lib1_core1_1_0_0",
        "core_file": SimpleUploadedFile("acme_lib1_core1_1_0_0.core", b"CAPI=2:\nname: Acme:Lib1:Core1:1.0.0\n"),
        "sig_url": None,
        "description": "A test core package.",
        # No spdx_license field
        "core_content_yaml": {
            "filesets": {
                "fs1": {
                    "files": ["file1.v"],
                    "file_type": "verilogSource"
                }
            },
            "targets": {
                "sim": {
                    "filesets": ["fs1"],
                    "parameters": {"param1": "value"},
                    "default_tool": "icarus",
                    "flow": "simflow",
                    "description": "Simulation target"
                }
            }
        }
    }   
    serializer = CoreSerializer()
    instance = serializer.create(validated_data)
    assert isinstance(instance, CorePackage)
    assert instance.spdx_license is None or instance.spdx_license == ""

@pytest.mark.django_db
def test_validate_against_schema_validation_error(tmp_path):
    s = CoreSerializer()
    # Patch open, json.load, and validate to raise ValidationError
    with mock.patch("builtins.open", mock.mock_open(read_data="{}")), \
         mock.patch("json.load", return_value={}), \
         mock.patch("core_directory.serializers.validate", side_effect=JsonSchemaValidationError("fail")):
        with pytest.raises(serializers.ValidationError) as excinfo:
            s._validate_against_schema({}, "dummy_schema.json", "core")
        assert "Validation error in core" in str(excinfo.value)

@pytest.mark.django_db
def test_validate_against_schema_schema_error(tmp_path):
    s = CoreSerializer()
    with mock.patch("builtins.open", mock.mock_open(read_data="{}")), \
         mock.patch("json.load", return_value={}), \
         mock.patch("core_directory.serializers.validate", side_effect=SchemaError("bad schema")):
        with pytest.raises(serializers.ValidationError) as excinfo:
            s._validate_against_schema({}, "dummy_schema.json", "core")
        assert "Internal error: invalid schema to validate core" in str(excinfo.value)

@pytest.mark.django_db
def test_validate_against_schema_jsondecodeerror(tmp_path):
    s = CoreSerializer()
    # Patch json.load to raise JSONDecodeError
    with mock.patch("builtins.open", mock.mock_open(read_data="{}")), \
         mock.patch("json.load", side_effect=json.decoder.JSONDecodeError("fail", "doc", 0)):
        with pytest.raises(serializers.ValidationError) as excinfo:
            s._validate_against_schema({}, "dummy_schema.json", "core")
        assert "Internal error: invalid schema to validate core" in str(excinfo.value)

@pytest.mark.django_db
def test_core_serializer_update_noop():
    serializer = CoreSerializer()
    vendor = Vendor.objects.create(name="Acme")
    validated_data = {"name": "NewName"}
    result = serializer.update(vendor, validated_data)
    assert result is None  # The method does nothing and returns None
    # Optionally, check that the instance is unchanged
    vendor.refresh_from_db()
    assert vendor.name == "Acme"

