import pytest
from django.urls import reverse
from core_directory.models import Vendor, Library, Project, CorePackage

@pytest.mark.django_db
def test_cores_success(client, mocker):
    url = reverse('core_directory:core_list')
    # Mock the queryset to return a list of vlnv_names
    mock_qs = mocker.Mock()
    mock_qs.order_by.return_value = mock_qs
    mock_qs.values_list.return_value = ["acme:lib1:core1:1.0.0"]
    mock_filter = mocker.patch("core_directory.models.CorePackage.objects.filter", return_value=mock_qs)

    response = client.get(url)
    assert response.status_code == 200
    assert response.json() == ["acme:lib1:core1:1.0.0"]
    mock_filter.assert_called_once_with(vlnv_name__icontains="")

@pytest.mark.django_db
def test_multiple_cores_success(client):
    # Set up test data: two cores in the database
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    project1 = Project.objects.create(vendor=vendor, library=library, name="Core1", description="desc")
    project2 = Project.objects.create(vendor=vendor, library=library, name="Core2", description="desc")
    CorePackage.objects.create(
        project=project1,
        vlnv_name="acme:lib1:core1:1.0.0",
        version="1.0.0",
        version_major=1,
        version_minor=0,
        version_patch=0,
        core_url="https://example.com/core1",
        description="desc"
    )
    CorePackage.objects.create(
        project=project2,
        vlnv_name="acme:lib1:core2:1.0.0",
        version="1.0.0",
        version_major=1,
        version_minor=0,
        version_patch=0,
        core_url="https://example.com/core2_v1.0.0",
        description="desc"
    )
    CorePackage.objects.create(
        project=project2,
        vlnv_name="acme:lib1:core2:0.1.0",
        version="0.1.0",
        version_major=0,
        version_minor=1,
        version_patch=0,
        core_url="https://example.com/core2_v0.1.0",
        description="desc"
    )

    url = reverse('core_directory:core_list')
    response = client.get(url)
    assert response.status_code == 200
    # The API returns a list of vlnv_names
    assert set(response.json()) == {"acme:lib1:core1:1.0.0", "acme:lib1:core2:0.1.0", "acme:lib1:core2:1.0.0"}

@pytest.mark.django_db
def test_cores_with_filter(client):
    # Set up test data: two cores in the database
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    project1 = Project.objects.create(vendor=vendor, library=library, name="foo_core", description="desc")
    project2 = Project.objects.create(vendor=vendor, library=library, name="bar_core", description="desc")
    cp1 = CorePackage.objects.create(
        project=project1,
        vlnv_name="acme:lib1:foo_core:1.0.0",
        version="1.0.0",
        version_major=1,
        version_minor=0,
        version_patch=0,
        core_url="https://example.com/foo_core",
        description="desc"
    )
    cp2 = CorePackage.objects.create(
        project=project2,
        vlnv_name="acme:lib1:bar_core:1.0.0",
        version="1.0.0",
        version_major=1,
        version_minor=0,
        version_patch=0,
        core_url="https://example.com/bar_core",
        description="desc"
    )

    url = reverse('core_directory:core_list')

    # Apply filter 'foo'
    response = client.get(url, {"filter": "foo"})
    assert response.status_code == 200
    assert response.json() == ["acme:lib1:foo_core:1.0.0"]

    # Apply filter 'bar'
    response = client.get(url, {"filter": "bar"})
    assert response.status_code == 200
    assert response.json() == ["acme:lib1:bar_core:1.0.0"]

    # Apply filter that matches nothing
    response = client.get(url, {"filter": "baz"})
    assert response.status_code == 200
    assert response.json() == []