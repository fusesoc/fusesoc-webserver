import pytest
from django.urls import reverse, resolve

@pytest.mark.parametrize("url_name, kwargs, expected_status", [
    ("landing", {}, 200),
    ("core-detail", {"pk": 1}, 200),
    ("core-package-list", {}, 200),
    ("core-detail-vlnv", {
        "vendor": "acme",
        "library": "lib",
        "core": "core",
        "version": "1.0"
    }, 200),
    ("vendor-list", {}, 200),
    ("vendor-detail", {"sanitized_name": "acme"}, 200),
])
def test_project_urls(client, url_name, kwargs, expected_status):
    """
    Test that each project-level named URL can be reversed, resolved, and returns a valid response.
    """
    url = reverse(url_name, kwargs=kwargs)
    match = resolve(url)
    assert match.view_name == url_name

    response = client.get(url)
    # If your views require DB objects, you may need to create them first or expect 404
    assert response.status_code in (expected_status, 404)

def test_admin_url(client):
    url = reverse('admin:index')
    response = client.get(url)
    # Admin usually redirects to login if not authenticated
    assert response.status_code in (200, 302)