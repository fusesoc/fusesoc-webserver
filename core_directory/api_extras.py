"""
Custom throttling classes and OpenAPI schema hooks for the core_directory API.

Includes:
- Custom anonymous user rate throttle with user-friendly error messages.
- OpenAPI postprocessing hook to add 'Retry-After' header to 429 responses.
"""

from rest_framework.throttling import AnonRateThrottle
from rest_framework.exceptions import Throttled

class ApiAnonRateThrottle(AnonRateThrottle):
    """
    Throttle class for anonymous API users.

    Returns a custom error message with the wait time when the rate limit is exceeded.
    """
    def throttle_failure(self):
        wait = self.wait()
        if wait is not None:
            minutes, seconds = divmod(int(wait), 60)
            if minutes:
                wait_str = f"{minutes} minute(s) and {seconds} second(s)"
            else:
                wait_str = f"{seconds} second(s)"
            detail = (
                f"API rate limit reached. "
                f"Please try again in {wait_str}."
            )
        else:
            detail = "API rate limit reached. Please try again later."
        raise Throttled(detail=detail, wait=wait)

def add_retry_after_header_to_429_responses(result, generator, request, public):
    # pylint: disable=unused-argument
    """
    Add 'Retry-After' header to all 429 responses in the OpenAPI schema.
    """
    for _path, path_item in result.get('paths', {}).items():
        for operation in path_item.values():
            responses = operation.get('responses', {})
            if '429' in responses:
                headers = responses['429'].setdefault('headers', {})
                headers['Retry-After'] = {
                    'description': 'Seconds to wait before making a new request.',
                    'schema': {'type': 'integer'}
                }
    return result
