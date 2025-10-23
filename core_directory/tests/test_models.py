import pytest
from rest_framework import serializers
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from core_directory.models import (
    Vendor, Library, Project, CorePackage, Fileset, FilesetDependency, Target, TargetConfiguration
)
from core_directory.serializers import CoreSerializer
from utils.spdx import get_spdx_license_url, get_spdx_license_ids

@pytest.mark.django_db
def test_vendor_creation_and_str():
    v = Vendor.objects.create(name="Acme")
    assert v.sanitized_name == "acme"
    assert str(v) == "Acme"

@pytest.mark.django_db
def test_library_creation_and_str():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    assert lib.sanitized_name == "lib1"
    assert str(lib) == f"{v}:Lib1"

@pytest.mark.django_db
def test_project_creation_and_str():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    proj = Project.objects.create(vendor=v, library=lib, name="Core1", description="desc")
    assert proj.sanitized_name == "core1"
    assert str(proj) == "Acme:Lib1:Core1"

@pytest.mark.django_db
def test_corepackage_creation_and_version_parsing():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    proj = Project.objects.create(vendor=v, library=lib, name="Core1", description="desc")
    cp = CorePackage.objects.create(
        project=proj,
        vlnv_name="acme:lib1:core1:1.2.3-rc1",
        version="1.2.3-rc1",
        core_file="test.core",
        description="desc"
    )
    assert cp.version_major == 1
    assert cp.version_minor == 2
    assert cp.version_patch == 3
    assert cp.version_prerelease == "rc1"
    assert str(cp) == f"{proj}:1.2.3-rc1"
    assert not cp.is_signed
    # Now add sig_url
    cp.signature_file = "test.core.sig"
    cp.save()
    assert cp.is_signed

@pytest.mark.django_db
def test_corepackage_invalid_version():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    proj = Project.objects.create(vendor=v, library=lib, name="Core1", description="desc")
    cp = CorePackage(
        project=proj,
        vlnv_name="acme:lib1:core1:bad",
        version="bad",
        core_file="test.core",
        description="desc"
    )
    with pytest.raises(ValidationError):
        cp.save()

@pytest.mark.django_db
def test_unique_constraints():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    proj = Project.objects.create(vendor=v, library=lib, name="Core1", description="desc")
    CorePackage.objects.create(
        project=proj,
        vlnv_name="acme:lib1:core1:1.2.3",
        version="1.2.3",
        core_file="test.core",
        description="desc"
    )
    # Duplicate version for same project should fail
    with pytest.raises(ValidationError):
        CorePackage.objects.create(
            project=proj,
            vlnv_name="acme:lib1:core1:1.2.3",
            version="1.2.3",
        core_file="test.core",
            description="desc"
        )

@pytest.mark.django_db
def test_fileset_and_dependency():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    proj = Project.objects.create(vendor=v, library=lib, name="Core1", description="desc")
    cp = CorePackage.objects.create(
        project=proj,
        vlnv_name="acme:lib1:core1:1.2.3",
        version="1.2.3",
        core_file="test.core",
        description="desc"
    )
    fs = Fileset.objects.create(core_package=cp, name="fs1")
    dep = FilesetDependency.objects.create(
        fileset=fs,
        dependency_core_name="othercore",
        core_package=cp
    )
    assert str(fs) == f"{cp}:fs1"
    assert "depends on othercore" in str(dep)

@pytest.mark.django_db
def test_target_and_target_configuration():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    proj = Project.objects.create(vendor=v, library=lib, name="Core1", description="desc")
    cp = CorePackage.objects.create(
        project=proj,
        vlnv_name="acme:lib1:core1:1.2.3",
        version="1.2.3",
        core_file="test.core",
        description="desc"
    )
    fs = Fileset.objects.create(core_package=cp, name="fs1")
    tgt = Target.objects.create(name="sim")
    tc = TargetConfiguration.objects.create(core_package=cp, target=tgt)
    tc.filesets.add(fs)
    assert str(tgt) == "sim"
    assert str(tc) == f"{cp}:sim"
    assert fs in tc.filesets.all()

@pytest.mark.django_db
def test_corepackage_with_valid_spdx_license():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    proj = Project.objects.create(vendor=v, library=lib, name="Core1", description="desc")
    valid_license = next(iter(get_spdx_license_ids()))
    cp = CorePackage.objects.create(
        project=proj,
        vlnv_name="acme:lib1:core1:1.0.0",
        version="1.0.0",
        core_file="test.core",
        description="desc",
        spdx_license=valid_license
    )
    assert cp.spdx_license == valid_license
    assert cp.get_license_url() == get_spdx_license_url(valid_license)

@pytest.mark.django_db
def test_corepackage_with_license_ref_fails():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    proj = Project.objects.create(vendor=v, library=lib, name="Core1", description="desc")
    cp = CorePackage(
        project=proj,
        vlnv_name="acme:lib1:core1:2.0.0",
        version="2.0.0",
        core_file="test.core",
        description="desc",
        spdx_license="LicenseRef-MyCustomLicense"
    )
    with pytest.raises(ValidationError):
        cp.save()

@pytest.mark.django_db
def test_corepackage_with_invalid_license_fails():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    proj = Project.objects.create(vendor=v, library=lib, name="Core1", description="desc")
    cp = CorePackage(
        project=proj,
        vlnv_name="acme:lib1:core1:3.0.0",
        version="3.0.0",
        core_file="test.core",
        description="desc",
        spdx_license="NOT_A_VALID_LICENSE"
    )
    with pytest.raises(ValidationError):
        cp.save()

@pytest.mark.django_db
def test_corepackage_with_blank_license():
    v = Vendor.objects.create(name="Acme")
    lib = Library.objects.create(vendor=v, name="Lib1")
    proj = Project.objects.create(vendor=v, library=lib, name="Core1", description="desc")
    cp = CorePackage.objects.create(
        project=proj,
        vlnv_name="acme:lib1:core1:4.0.0",
        version="4.0.0",
        core_file="test.core",
        description="desc"
    )
    assert cp.spdx_license is None or cp.spdx_license == ""
    assert cp.get_license_url() is None
