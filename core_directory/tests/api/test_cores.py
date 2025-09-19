from unittest import mock
import pytest
from django.urls import reverse

@pytest.mark.django_db
@mock.patch("core_directory.views.api_views.Github")
def test_cores_success(mock_github, client, mocker):
    url = reverse('core_directory:core_list')
    # Mock GitHub repo and contents
    mock_repo = mock.Mock()
    mock_content = mock.Mock()
    mock_content.type = "file"
    mock_content.path = "foo.core"
    mock_repo.get_contents.return_value = [mock_content]
    mock_github.return_value.get_repo.return_value = mock_repo
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)

    response = client.get(url)
    assert response.status_code == 200
    assert response.json() == ["foo"]

@pytest.mark.django_db
def test_cores_github_exception(client, mocker):
    url = reverse('core_directory:core_list')
    mock_repo = mocker.Mock()
    # Define a mock exception with a .data attribute
    class GithubException(Exception):
        def __init__(self):
            self.data = "fail"
    mock_repo.get_contents.side_effect = GithubException()
    mock_github = mocker.patch("core_directory.views.api_views.Github")
    mock_github.return_value.get_repo.return_value = mock_repo
    mocker.patch("core_directory.views.api_views.GithubException", GithubException)
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)

    response = client.get(url)
    assert response.status_code == 500
    assert "GitHub error" in str(response.content)
    assert "fail" in str(response.content)

import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_cores_with_filter(client, mocker):
    url = reverse('core_directory:core_list')
    mock_repo = mocker.Mock()
    # Simulate two core files, only one matches the filter
    mock_content1 = mocker.Mock()
    mock_content1.type = "file"
    mock_content1.path = "foo.core"
    mock_content2 = mocker.Mock()
    mock_content2.type = "file"
    mock_content2.path = "bar.core"
    mock_repo.get_contents.return_value = [mock_content1, mock_content2]
    mock_github = mocker.patch("core_directory.views.api_views.Github")
    mock_github.return_value.get_repo.return_value = mock_repo
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)

    # Apply filter 'foo'
    response = client.get(url, {"filter": "foo"})
    assert response.status_code == 200
    data = response.json()
    assert data == ["foo"]
    # Apply filter 'bar'
    response = client.get(url, {"filter": "bar"})
    assert response.status_code == 200
    data = response.json()
    assert data == ["bar"]
    # Apply filter that matches nothing
    response = client.get(url, {"filter": "baz"})
    assert response.status_code == 200
    data = response.json()
    assert data == []
