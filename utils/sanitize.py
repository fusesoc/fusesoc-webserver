"""
Utility functions for sanitizing strings and generating unique sanitized names
for Django model fields, such as file names or slugs.
"""
import re

def sanitize_string(string):
    """
    Sanitize a given string to make it a valid, lowercase file name.

    This function replaces invalid characters in the input string with underscores,
    converts to lowercaseand ensures the resulting string does not exceed a specified
    maximum length.

    Invalid characters include: `/`, `\\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`, and spaces.

    Parameters
    ----------
    string : str
        The input string to be sanitized.

    Returns
    -------
    str
        A sanitized version of the input string, suitable for use as a file name.
        The sanitized string will be lowercase, will have all invalid characters
        replaced with underscores and will be truncated to a maximum length of
        255 characters if necessary.

    Example
    -------
    >>> sanitize_string("Example: Invalid/File*Name?.txt")
    'example__invalid_file_name_.txt'
    """
    invalid_chars = r'[\/\\:*?"<>| ]'
    max_length = 255

    # Replace invalid characters with an underscore and convert to lowercase
    sanitized_string = re.sub(invalid_chars, '_', string).lower()

    # Truncate the string to the maximum allowed length
    if len(sanitized_string) > max_length:
        sanitized_string = sanitized_string[:max_length]

    return sanitized_string

def get_unique_sanitized_name(model, name, field='sanitized_name', instance=None):
    """
    Generate a unique sanitized name for a Django model instance.

    This function sanitizes the provided name and ensures its uniqueness within the specified model.
    If a conflict is found, a numeric suffix is appended to the base sanitized name until a unique
    value is found. Optionally, an existing instance can be excluded from the uniqueness check
    (useful for updates).

    Parameters
    ----------
    model : django.db.models.Model
        The Django model class to check for uniqueness.
    name : str
        The input name to be sanitized and made unique.
    field : str, optional
        The model field to check for uniqueness (default is 'sanitized_name').
    instance : django.db.models.Model, optional
        An existing instance to exclude from the uniqueness check (default is None).

    Returns
    -------
    str
        A unique, sanitized version of the input name suitable for use as a model field value.

    Example
    -------
    >>> get_unique_sanitized_name(MyModel, "Example: Name")
    'example__name'
    """
    base = sanitize_string(name)
    sanitized = base
    prefix = 1
    qs = model.objects.all()
    if instance and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(**{field: sanitized}).exists():
        sanitized = f"{base}_{prefix}"
        prefix += 1
    return sanitized
