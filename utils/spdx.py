"""
SPDX License Utilities

This module provides functions and constants for working with SPDX license identifiers
in the Django project. It includes utilities to load and cache the official SPDX license
list, generate choices for model fields, and validate license identifiers (excluding
support for custom LicenseRef- identifiers).

Typical usage:
    from utils.spdx import get_spdx_choices, validate_spdx

Functions:
    get_spdx_license_ids()   -- Returns a set of SPDX license IDs (empty set if file missing/invalid).
    get_spdx_choices()       -- Returns a list of (license_id, license_id) tuples for Django fields.
    get_spdx_license_url()   -- Returns the details URL for a given SPDX license ID, or None if not found.
    validate_spdx()          -- Validator for SPDX identifiers.


The SPDX license list (licenses.json) should be kept up to date using the management
command or other update mechanism.
"""

import json
from functools import lru_cache
from django.conf import settings
from django.core.exceptions import ValidationError

@lru_cache(maxsize=1)
def _load_spdx_license_data():
    """
    Loads and caches the SPDX license data from the JSON file.
    Returns a dict: {licenseId: license_data_dict}
    """
    try:
        with open(settings.SPDX_LICENSES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {lic['licenseId']: lic for lic in data['licenses']}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def get_spdx_license_ids():
    """
    Returns a set of all SPDX license IDs.
    """
    return set(_load_spdx_license_data().keys())

def get_spdx_choices():
    """
    Returns a list of (license_id, license_id) tuples for use in Django fields.
    """
    return [(lic, lic) for lic in sorted(get_spdx_license_ids())]

def get_spdx_license_url(license_id):
    """
    Returns the details URL for a given SPDX license ID, or None if not found.
    """
    lic = _load_spdx_license_data().get(license_id)
    if lic:
        return lic.get('seeAlso', [None])[0] or lic.get('reference')
    return None

def validate_spdx(value):
    """
    Validator for SPDX license IDs or custom LicenseRef- identifiers.
    Raises ValidationError if invalid.
    """
    if value not in get_spdx_license_ids():
        raise ValidationError(f"{value} is not a valid SPDX license identifier.")
