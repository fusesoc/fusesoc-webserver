# tests/test_sitemaps.py

import pytest
from django.urls import reverse, NoReverseMatch
from django.conf import settings
from django.test import override_settings

from core_directory.models import Vendor, Library, Project, CorePackage

@pytest.mark.django_db
@override_settings(INDEXABLE=True)
def test_sitemap_with_data(client):
    # Create test data
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    project = Project.objects.create(vendor=vendor, library=library, name="Core1", description="desc")
    core_package = CorePackage.objects.create(
        project=project,
        vlnv_name="acme:lib1:core1:1.0.0",
        version="1.0.0",
        core_file="acme_lib1_core1_1_0_0.core",
        description="desc"
    )

    # The sitemap should be available
    url = reverse("sitemap")
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()

    # Check for expected URLs in the sitemap
    assert "<urlset" in content
    # Vendor page
    assert vendor.get_absolute_url() in content
    # CorePackage page
    assert core_package.get_absolute_url() in content
    # Static views
    assert reverse("landing") in content
    assert reverse("core-package-list") in content
    assert reverse("vendor-list") in content

@pytest.mark.django_db
@override_settings(INDEXABLE=False)
def test_sitemap_not_available_when_indexing_disabled(client):
    url = reverse("sitemap")
    response = client.get(url)
    assert response.status_code == 404
