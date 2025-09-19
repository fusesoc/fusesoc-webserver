import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

@pytest.mark.django_db
def test_publish_success(client, mocker):
    url = reverse('core_directory:publish')
    # Mock serializer
    mock_serializer = mocker.patch("core_directory.views.api_views.CoreSerializer")
    instance = mock_serializer.return_value
    instance.is_valid.return_value = True
    instance.validated_data = {
        "vlnv_name": "vendor:lib:core:1.0.0",
        "core_file": SimpleUploadedFile("test.core", b"dummy"),
        "sanitized_name": "core",
        "signature_file": None,
    }
    # Mock github repo
    mock_repo = mocker.Mock()
    # Define a mock exception that matches the view's except block
    class GithubException(Exception):
        pass
    mock_repo.get_contents.side_effect = GithubException()
    mock_repo.create_file.return_value = {"content": mocker.Mock(download_url="https://example.com/core")}
    mock_github = mocker.patch("core_directory.views.api_views.Github")
    mock_github.return_value.get_repo.return_value = mock_repo
    mocker.patch("core_directory.views.api_views.GithubException", GithubException)
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)

    response = client.post(url, data={"core_file": SimpleUploadedFile("test.core", b"dummy")})
    assert response.status_code in (200, 201)
    assert b"published" in response.content or b"valid" in response.content

@pytest.mark.django_db
def test_publish_already_exists(client, mocker):
    url = reverse('core_directory:publish')
    mock_serializer = mocker.patch("core_directory.views.api_views.CoreSerializer")
    instance = mock_serializer.return_value
    instance.is_valid.return_value = True
    instance.validated_data = {
        "vlnv_name": "vendor:lib:core:1.0.0",
        "core_file": SimpleUploadedFile("test.core", b"dummy"),
        "sanitized_name": "core",
        "signature_file": None,
    }
    mock_repo = mocker.Mock()
    mock_repo.get_contents.return_value = True  # Simulate file exists
    mock_github = mocker.patch("core_directory.views.api_views.Github")
    mock_github.return_value.get_repo.return_value = mock_repo
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)

    response = client.post(url, data={"core_file": SimpleUploadedFile("test.core", b"dummy")})
    assert response.status_code == 409
    assert b"already exists" in response.content

@pytest.mark.django_db
def test_publish_github_error(client, mocker):
    url = reverse('core_directory:publish')
    mock_serializer = mocker.patch("core_directory.views.api_views.CoreSerializer")
    instance = mock_serializer.return_value
    instance.is_valid.return_value = True
    instance.validated_data = {
        "vlnv_name": "vendor:lib:core:1.0.0",
        "core_file": SimpleUploadedFile("test.core", b"dummy"),
        "sanitized_name": "core",
        "signature_file": None,
    }
    class UnknownObjectException(Exception):
        pass
    class GithubException(Exception):
        data = "fail"
    mock_repo = mocker.Mock()
    # Raise UnknownObjectException to enter the except block
    mock_repo.get_contents.side_effect = UnknownObjectException()
    # Raise GithubException from create_file to simulate a GitHub error
    mock_repo.create_file.side_effect = GithubException()
    mock_github = mocker.patch("core_directory.views.api_views.Github")
    mock_github.return_value.get_repo.return_value = mock_repo
    mocker.patch("core_directory.views.api_views.UnknownObjectException", UnknownObjectException)
    mocker.patch("core_directory.views.api_views.GithubException", GithubException)
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)

    response = client.post(url, data={"core_file": SimpleUploadedFile("test.core", b"dummy")})
    assert response.status_code == 500
    assert b"GitHub error" in response.content or b"fail" in response.content

@pytest.mark.django_db
def test_publish_invalid_serializer(client, mocker):
    url = reverse('core_directory:publish')
    mock_serializer = mocker.patch("core_directory.views.api_views.CoreSerializer")
    instance = mock_serializer.return_value
    instance.is_valid.return_value = False
    instance.errors = {"field": ["error"]}
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)
    response = client.post(url, data={"core_file": SimpleUploadedFile("test.core", b"dummy")})
    assert response.status_code == 400
    assert b"error" in response.content

@pytest.mark.django_db
def test_publish_with_signature(client, mocker):
    url = reverse('core_directory:publish')
    # Mock serializer
    mock_serializer = mocker.patch("core_directory.views.api_views.CoreSerializer")
    instance = mock_serializer.return_value
    instance.is_valid.return_value = True
    instance.validated_data = {
        "vlnv_name": "vendor:lib:core:1.0.0",
        "core_file": SimpleUploadedFile("test.core", b"dummy core"),
        "sanitized_name": "core",
        "signature_file": SimpleUploadedFile("test.core.sig", b"dummy sig"),
    }
    # Mock github repo
    mock_repo = mocker.Mock()
    class UnknownObjectException(Exception):
        pass
    mock_repo.get_contents.side_effect = UnknownObjectException()
    # Simulate create_file for core and signature
    mock_repo.create_file.side_effect = [
        {"content": mocker.Mock(download_url="https://example.com/core")},
        {"content": mocker.Mock(download_url="https://example.com/core.sig")},
    ]
    mock_github = mocker.patch("core_directory.views.api_views.Github")
    mock_github.return_value.get_repo.return_value = mock_repo
    mocker.patch("core_directory.views.api_views.UnknownObjectException", UnknownObjectException)
    mocker.patch("os.getenv", side_effect=lambda key, default=None: "dummy_token" if key == "GITHUB_ACCESS_TOKEN" else default)

    response = client.post(
        url,
        data={
            "core_file": SimpleUploadedFile("test.core", b"dummy core"),
            "signature_file": SimpleUploadedFile("test.core.sig", b"dummy sig"),
        }
    )
    assert response.status_code in (200, 201)
    assert b"published" in response.content or b"valid" in response.content
    # Optionally, check that create_file was called twice (core and sig)
    assert mock_repo.create_file.call_count == 2