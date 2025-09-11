import pytest
from django.urls import reverse, resolve

@pytest.mark.django_db
@pytest.mark.parametrize("url_name, kwargs, expected_status, needs_object, method", [
    ("redirect_to_docs", {}, 301, False, "get"),
    ("health_check", {}, 200, False, "get"),
    ("core_list", {}, 200, False, "get"),
    ("core_get", {"package_name": "example"}, 200, False, "get"),
    ("validate", {}, 400, False, "post"),
    ("publish", {}, 400, False, "post"),
    ("api_docs_landing", {}, 200, False, "get"),
    ("schema", {}, 200, False, "get"),
    ("swagger_ui", {}, 200, False, "get"),
    ("redoc_ui", {}, 200, False, "get"),
])
def test_url_resolves_and_returns(client, mocker, url_name, kwargs, expected_status, needs_object, method):
    """
    Test that each named URL can be reversed, resolved, and returns a valid response.
    For core_get and core_list, mock the GitHub API call.
    """
    mocker.patch.dict("os.environ", {
        "GITHUB_REPO": "dummy/repo",
        "GITHUB_ACCESS_TOKEN": "dummy_token"
    })

    # Mock GitHub for endpoints that use it
    if url_name in ("core_get", "core_list"):
        mock_github = mocker.patch("core_directory.views.api_views.Github")
        mock_repo = mock_github.return_value.get_repo.return_value
        if url_name == "core_get":
            mock_contents = mocker.Mock()
            mock_contents.decoded_content = b"dummy core file content"
            mock_repo.get_contents.return_value = mock_contents
        elif url_name == "core_list":
            mock_content = mocker.Mock()
            mock_content.type = "file"
            mock_content.path = "foo.core"
            mock_repo.get_contents.return_value = [mock_content]

    url = reverse(f"core_directory:{url_name}", kwargs=kwargs)
    match = resolve(url)
    assert match.view_name == f"core_directory:{url_name}"

    if method == "get":
        response = client.get(url)
    elif method == "post":
        response = client.post(url, data={})
    else:
        raise ValueError(f"Unsupported method: {method}")

    assert response.status_code == expected_status
