"""
Utility functions for file and storage handling in the FuseSoC package database.

Includes helpers for working with Django FileFields and storage backends,
such as checking for file existence and avoiding duplicate uploads.
"""

from django.core.files.storage import default_storage

def filefield_value_for_storage(filename, fileobj):
    """
    Returns the correct value to assign to a FileField:
    - If the file exists in storage, returns the filename (string).
    - If not, returns the file object (triggers upload).
    """
    if fileobj is None:
        return None
    if default_storage.exists(filename):
        return filename
    return fileobj