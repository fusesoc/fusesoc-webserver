import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_api_docs_landing(client):
    url = reverse('core_directory:api_docs_landing')
    response = client.get(url)
    assert response.status_code == 200
    # Optionally check for template or content
    assert b"API" in response.content or b"Docs" in response.content

@pytest.mark.django_db
def test_health_check(client):
    url = reverse('core_directory:health_check')
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
