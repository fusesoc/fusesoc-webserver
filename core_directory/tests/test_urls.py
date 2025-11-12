import pytest
from django.urls import reverse, resolve

@pytest.mark.django_db
@pytest.mark.parametrize("url_name, kwargs, expected_status, needs_object, method", [
    ("redirect_to_docs", {}, 301, False, "get"),
    ("health_check", {}, 200, False, "get"),
    ("core_list", {}, 200, False, "get"),
    ("core_get", {}, 400, False, "get"),
    ("archive_get", {}, 200, False, "get"),
    ("validate", {}, 400, False, "post"),
    ("publish", {}, 400, False, "post"),
    ("api_docs_landing", {}, 200, False, "get"),
    ("schema", {}, 200, False, "get"),
    ("swagger_ui", {}, 200, False, "get"),
])
def test_url_resolves_and_returns(client, mocker, url_name, kwargs, expected_status, needs_object, method):
    """
    Test that each named URL can be reversed, resolved, and returns a valid response.
    For core_get and core_list, mock the GitHub API call.
    """
    
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
