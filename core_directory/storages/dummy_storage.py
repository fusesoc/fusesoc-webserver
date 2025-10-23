"""
DummyStorage for Django tests.

This in-memory storage backend is used to ensure that no files are written to disk
or external services during tests. All file operations are performed in memory.

Usage:
    Set DEFAULT_FILE_STORAGE = 'core_directory.storages.dummy_storage.DummyStorage'
    in your test settings to use this storage for all FileFields during tests.
"""

from django.core.files.storage import Storage
from django.core.files.base import ContentFile

class DummyStorage(Storage):
    """
    In-memory Django storage backend for use in tests.
    """
    _files = {}

    def _open(self, name, _mode='rb'):  # mode is required by Django Storage API
        return ContentFile(self._files.get(name, b''), name=name)

    def _save(self, name, content):
        content.seek(0)
        self._files[name] = content.read()
        return name

    def exists(self, name):
        return name in self._files

    def delete(self, name):
        if name in self._files:
            del self._files[name]

    def url(self, name):
        return f"/dummy/{name}"

    def get_accessed_time(self, name):
        """Not supported for DummyStorage."""
        raise NotImplementedError("get_accessed_time is not supported by DummyStorage.")

    def get_created_time(self, name):
        """Not supported for DummyStorage."""
        raise NotImplementedError("get_created_time is not supported by DummyStorage.")

    def get_modified_time(self, name):
        """Not supported for DummyStorage."""
        raise NotImplementedError("get_modified_time is not supported by DummyStorage.")

    def path(self, name):
        """Not supported for DummyStorage."""
        raise NotImplementedError("path() is not available for DummyStorage.")

    def listdir(self, path):
        """Not supported for DummyStorage."""
        raise NotImplementedError("listdir() is not available for DummyStorage.")

    def size(self, name):
        """Not supported for DummyStorage."""
        raise NotImplementedError("size() is not available for DummyStorage.")
