import pytest
from unittest import mock

from django.core.files.base import ContentFile

from utils.files import filefield_value_for_storage

def test_returns_none_if_fileobj_is_none():
    assert filefield_value_for_storage("foo.txt", None) is None

def test_returns_filename_if_exists(monkeypatch):
    # Patch default_storage.exists to return True
    monkeypatch.setattr("django.core.files.storage.default_storage.exists", lambda name: True)
    fileobj = ContentFile(b"dummy", name="foo.txt")
    result = filefield_value_for_storage("foo.txt", fileobj)
    assert result == "foo.txt"

def test_returns_fileobj_if_not_exists(monkeypatch):
    # Patch default_storage.exists to return False
    monkeypatch.setattr("django.core.files.storage.default_storage.exists", lambda name: False)
    fileobj = ContentFile(b"dummy", name="foo.txt")
    result = filefield_value_for_storage("foo.txt", fileobj)
    assert result is fileobj

def test_returns_fileobj_even_if_filename_differs(monkeypatch):
    # Patch default_storage.exists to return False
    monkeypatch.setattr("django.core.files.storage.default_storage.exists", lambda name: False)
    fileobj = ContentFile(b"dummy", name="bar.txt")
    result = filefield_value_for_storage("foo.txt", fileobj)
    assert result is fileobj

def test_returns_filename_even_if_fileobj_given(monkeypatch):
    # Patch default_storage.exists to return True
    monkeypatch.setattr("django.core.files.storage.default_storage.exists", lambda name: True)
    fileobj = ContentFile(b"dummy", name="bar.txt")
    result = filefield_value_for_storage("foo.txt", fileobj)
    assert result == "foo.txt"
