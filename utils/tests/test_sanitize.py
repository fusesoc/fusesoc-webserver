import pytest
from utils.sanitize import sanitize_string, get_unique_sanitized_name
from core_directory.models import Vendor  # Use your real model with sanitized_name

# --- Tests for sanitize_string ---

@pytest.mark.parametrize("input_str,expected", [
    ("Example: Invalid/File*Name?.txt", "example__invalid_file_name_.txt"),
    ("Hello World!", "hello_world!"),
    ("A/B\\C:D*E?F\"G<H>I|J K", "a_b_c_d_e_f_g_h_i_j_k"),
    ("Already_clean.txt", "already_clean.txt"),
    ("   Spaces   ", "___spaces___"),
    ("", ""),
    ("a" * 300, "a" * 255),  # Should be truncated to 255 chars
])
def test_sanitize_string(input_str, expected):
    assert sanitize_string(input_str) == expected

# --- Tests for get_unique_sanitized_name using Vendor model ---

@pytest.mark.django_db
def test_get_unique_sanitized_name_unique():
    # No Vendor with this sanitized_name yet
    result = get_unique_sanitized_name(Vendor, "Test Name")
    assert result == "test_name"

@pytest.mark.django_db
def test_get_unique_sanitized_name_conflict():
    Vendor.objects.create(name="Vendor1", sanitized_name="test_name")
    result = get_unique_sanitized_name(Vendor, "Test Name")
    assert result == "test_name_1"

@pytest.mark.django_db
def test_get_unique_sanitized_name_multiple_conflicts():
    Vendor.objects.create(name="Vendor1", sanitized_name="test_name")
    Vendor.objects.create(name="Vendor2", sanitized_name="test_name_1")
    Vendor.objects.create(name="Vendor3", sanitized_name="test_name_2")
    result = get_unique_sanitized_name(Vendor, "Test Name")
    assert result == "test_name_3"

@pytest.mark.django_db
def test_get_unique_sanitized_name_exclude_instance():
    # Create a Vendor
    vendor = Vendor.objects.create(name="Vendor1", sanitized_name="test_name")
    # Should not conflict with itself
    result = get_unique_sanitized_name(Vendor, "Test Name", instance=vendor)
    assert result == "test_name"
