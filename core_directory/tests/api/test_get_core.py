import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_getcore_success(client, mocker):
    url = reverse('core_directory:core_get', kwargs={"package_name": "foo"})
    # Mock the repo and content
    mock_repo = mocker.Mock()
    mock_content = mocker.Mock()
    mock_content.decoded_content = b"core content"
    mock_repo.get_contents.return_value = mock_content
    mock_github = mocker.patch("core_directory.views.api_views.Github")
    mock_github.return_value.get_repo.return_value = mock_repo
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)

    response = client.get(url)
    assert response.status_code == 200
    assert b"core content" in response.content
    assert response["Content-Disposition"].endswith("foo.core")

@pytest.mark.django_db
def test_getcore_not_found(client, mocker):
    url = reverse('core_directory:core_get', kwargs={"package_name": "foo"})
    mock_repo = mocker.Mock()
    class NotFound(Exception):
        status = 404
        data = "not found"
    mock_repo.get_contents.side_effect = NotFound()
    mock_github = mocker.patch("core_directory.views.api_views.Github")
    mock_github.return_value.get_repo.return_value = mock_repo
    mocker.patch("core_directory.views.api_views.GithubException", NotFound)
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)

    response = client.get(url)
    assert response.status_code == 404
    assert "not found" in str(response.content)

import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_getcore_github_exception(client, mocker):
    url = reverse('core_directory:core_get', kwargs={"package_name": "foo"})

    # Define a mock GithubException with .status and .data attributes
    class GithubException(Exception):
        def __init__(self, status=500, data="fail"):
            self.status = status
            self.data = data

    mock_repo = mocker.Mock()
    mock_repo.get_contents.side_effect = GithubException(500, "fail")
    mock_github = mocker.patch("core_directory.views.api_views.Github")
    mock_github.return_value.get_repo.return_value = mock_repo
    mocker.patch("core_directory.views.api_views.GithubException", GithubException)
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)

    response = client.get(url)
    assert response.status_code == 500
    assert b"GitHub error" in response.content
    assert b"fail" in response.content