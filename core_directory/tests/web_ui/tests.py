import pytest
from django.http import Http404
from django.test import RequestFactory
from django.urls import reverse
from core_directory.models import Vendor, Library, Project, CorePackage

@pytest.mark.django_db
def test_landing_view(client):
    Vendor.objects.create(name="Acme")
    Project.objects.create(
        vendor=Vendor.objects.first(),
        library=Library.objects.create(vendor=Vendor.objects.first(), name="Lib1"),
        name="Core1",
        description="desc"
    )
    url = reverse("landing")
    response = client.get(url)
    assert response.status_code == 200
    # Check the context, which is more robust than checking HTML
    assert response.context["num_cores"] == 1
    assert response.context["num_vendors"] == 1

@pytest.mark.django_db
def test_landing_view_two_cores(client):
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    # Create two projects (cores) under the same vendor and library
    Project.objects.create(vendor=vendor, library=library, name="Core1", description="desc")
    Project.objects.create(vendor=vendor, library=library, name="Core2", description="desc")
    url = reverse("landing")
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["num_cores"] == 2
    assert response.context["num_vendors"] == 1

@pytest.mark.django_db
def test_core_package_list_view(client):
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
    url = reverse("core-package-list")
    response = client.get(url)
    assert response.status_code == 200
    # Test search filter
    response = client.get(url, {"search": "core1"})
    assert response.status_code == 200

@pytest.mark.django_db
def test_vendor_list_view(client):
    v = Vendor.objects.create(name="Acme")
    url = reverse("vendor-list")
    response = client.get(url)
    assert response.status_code == 200
    # Test search filter
    response = client.get(url, {"search": "acme"})
    assert response.status_code == 200

@pytest.mark.django_db
def test_vendor_detail_view_by_pk(client):
    v = Vendor.objects.create(name="Acme")
    url = reverse("vendor-detail", kwargs={"sanitized_name": v.sanitized_name})
    response = client.get(url)
    assert response.status_code == 200

@pytest.mark.django_db
def test_vendor_detail_view_404(client):
    url = reverse("vendor-detail", kwargs={"sanitized_name": "doesnotexist"})
    response = client.get(url)
    assert response.status_code == 404