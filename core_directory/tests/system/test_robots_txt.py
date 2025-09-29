import pytest
from django.urls import reverse
from django.conf import settings

@pytest.mark.django_db
def test_robots_txt_indexable_true(settings, client):
    settings.INDEXABLE = True
    url = reverse("robots_txt")
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert "Disallow:" in response.content.decode()
    assert "Disallow: /" not in response.content.decode()

@pytest.mark.django_db
def test_robots_txt_indexable_false(settings, client):
    settings.INDEXABLE = False
    url = reverse("robots_txt")
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert "Disallow: /" in response.content.decode()