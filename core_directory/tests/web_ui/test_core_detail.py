import pytest
from django.http import Http404
from django.test import RequestFactory
from django.urls import reverse
from core_directory.models import Vendor, Library, Project, CorePackage, Fileset, Target, TargetConfiguration, FilesetDependency
from core_directory.views.web_views import core_detail

@pytest.mark.django_db
def test_core_detail_view_by_pk(client):
    v = Vendor.objects.create(name="Acme")
    l = Library.objects.create(vendor=v, name="Lib1")
    p = Project.objects.create(vendor=v, library=l, name="Core1", description="desc")
    cp = CorePackage.objects.create(
        project=p,
        vlnv_name="acme:lib1:core1:1.0.0",
        version="1.0.0",
        core_url="https://example.com/core",
        description="desc"
    )
    url = reverse("core-detail", kwargs={"pk": cp.pk})
    response = client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
@pytest.mark.django_db
def test_core_detail_no_argument():
    factory = RequestFactory()
    request = factory.get("/core/")
    with pytest.raises(Http404):
        core_detail(request)

@pytest.mark.django_db
def test_core_detail_by_vlnv_view(client):
    v = Vendor.objects.create(name="Acme")
    l = Library.objects.create(vendor=v, name="Lib1")
    p = Project.objects.create(vendor=v, library=l, name="Core1", description="desc")
    cp = CorePackage.objects.create(
        project=p,
        vlnv_name="acme:lib1:core1:1.0.0",
        version="1.0.0",
        core_url="https://example.com/core",
        description="desc"
    )
    url = reverse("core-detail-vlnv", kwargs={
        "vendor": v.sanitized_name,
        "library": l.sanitized_name,
        "core": p.sanitized_name,
        "version": cp.version
    })
    response = client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
def test_core_detail_by_vlnv_view_without_lib(client):
    v = Vendor.objects.create(name="Acme")
    l = Library.objects.create(vendor=v, name="")
    p = Project.objects.create(vendor=v, library=l, name="Core1", description="desc")
    cp = CorePackage.objects.create(
        project=p,
        vlnv_name="acme:lib1:core1:1.0.0",
        version="1.0.0",
        core_url="https://example.com/core",
        description="desc"
    )
    url = reverse("core-detail-vlnv", kwargs={
        "vendor": v.sanitized_name,
        "library": '~',
        "core": p.sanitized_name,
        "version": cp.version
    })
    response = client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
def test_core_detail_with_target_and_filesets(client):
    # Setup vendor, library, project, core package
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    project = Project.objects.create(vendor=vendor, library=library, name="Core1", description="desc")
    core_package = CorePackage.objects.create(
        project=project,
        vlnv_name="acme:lib1:core1:1.0.0",
        version="1.0.0",
        core_url="https://example.com/core",
        description="desc"
    )
    # Add fileset
    fileset = Fileset.objects.create(core_package=core_package, name="fs1", file_type="verilogSource")
    # Add dependency to fileset
    FilesetDependency.objects.create(
        fileset=fileset,
        dependency_core_name="othercore",
        core_package=core_package
    )
    # Add target
    target = Target.objects.create(name="sim")
    # Add target configuration and link fileset
    target_config = TargetConfiguration.objects.create(core_package=core_package, target=target)
    target_config.filesets.add(fileset)

    url = reverse("core-detail", kwargs={"pk": core_package.pk})
    response = client.get(url)
    assert response.status_code == 200

    # Check context for targets_with_deps
    targets_with_deps = response.context["targets_with_deps"]
    assert len(targets_with_deps) == 1
    t = targets_with_deps[0]
    assert t["target_configuration"] == target_config
    assert t["dependencies"] == ["othercore"]
    assert t["filetypes"] == ["verilogSource"]

@pytest.mark.django_db
def test_core_detail_unknown_core(client):
    # Use a PK that does not exist
    url = reverse("core-detail", kwargs={"pk": 99999})
    response = client.get(url)
    assert response.status_code == 404

@pytest.mark.django_db
def test_core_detail_by_vlnv_unknown_core(client):
    # Use vendor, library, core, and version values that do not exist
    url = reverse(
        "core-detail-vlnv",
        kwargs={
            "vendor": "unknownvendor",
            "library": "unknownlib",
            "core": "unknowncore",
            "version": "9.9.9"
        }
    )
    response = client.get(url)
    assert response.status_code == 404