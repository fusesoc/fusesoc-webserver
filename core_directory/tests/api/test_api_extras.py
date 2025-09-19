import pytest
from rest_framework.exceptions import Throttled
from core_directory.api_extras import ApiAnonRateThrottle, add_retry_after_header_to_429_responses

# --- Tests for ApiAnonRateThrottle ---

class DummyRequest:
    pass

def test_throttle_failure_with_wait(monkeypatch):
    throttle = ApiAnonRateThrottle()
    # Patch wait() to return 125 seconds (2 minutes, 5 seconds)
    monkeypatch.setattr(throttle, "wait", lambda: 125)
    with pytest.raises(Throttled) as excinfo:
        throttle.throttle_failure()
    assert "API rate limit reached" in str(excinfo.value)
    assert "2 minute(s) and 5 second(s)" in str(excinfo.value)
    assert excinfo.value.wait == 125

def test_throttle_failure_with_wait_seconds(monkeypatch):
    throttle = ApiAnonRateThrottle()
    # Patch wait() to return 45 seconds
    monkeypatch.setattr(throttle, "wait", lambda: 45)
    with pytest.raises(Throttled) as excinfo:
        throttle.throttle_failure()
    assert "API rate limit reached" in str(excinfo.value)
    assert "45 second(s)" in str(excinfo.value)
    assert excinfo.value.wait == 45

def test_throttle_failure_without_wait(monkeypatch):
    throttle = ApiAnonRateThrottle()
    # Patch wait() to return None
    monkeypatch.setattr(throttle, "wait", lambda: None)
    with pytest.raises(Throttled) as excinfo:
        throttle.throttle_failure()
    assert "API rate limit reached" in str(excinfo.value)
    assert "Please try again later" in str(excinfo.value)
    assert excinfo.value.wait is None

# --- Tests for add_retry_after_header_to_429_responses ---

def test_add_retry_after_header_to_429_responses():
    # Simulate a minimal OpenAPI result dict
    result = {
        "paths": {
            "/api/endpoint/": {
                "get": {
                    "responses": {
                        "429": {
                            "description": "Too Many Requests"
                        }
                    }
                }
            }
        }
    }
    updated = add_retry_after_header_to_429_responses(result, None, None, None)
    headers = updated["paths"]["/api/endpoint/"]["get"]["responses"]["429"]["headers"]
    assert "Retry-After" in headers
    assert headers["Retry-After"]["description"] == "Seconds to wait before making a new request."
    assert headers["Retry-After"]["schema"]["type"] == "integer"

def test_add_retry_after_header_to_429_responses_no_429():
    # No 429 response present
    result = {
        "paths": {
            "/api/endpoint/": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "OK"
                        }
                    }
                }
            }
        }
    }
    updated = add_retry_after_header_to_429_responses(result, None, None, None)
    # Should not add anything if 429 is not present
    assert "headers" not in updated["paths"]["/api/endpoint/"]["get"]["responses"].get("200", {})
