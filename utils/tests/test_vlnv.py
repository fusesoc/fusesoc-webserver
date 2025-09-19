import pytest
from utils.vlnv import VLNV

def test_from_string_full():
    v = VLNV.from_string("vendor:library:name:1.2.3")
    assert v.vendor == "vendor"
    assert v.library == "library"
    assert v.name == "name"
    assert v.version == "1.2.3"
    assert v.to_string() == "vendor:library:name:1.2.3"

def test_from_string_missing_vendor():
    v = VLNV.from_string("library:name:1.2.3")
    assert v.vendor is None
    assert v.library == "library"
    assert v.name == "name"
    assert v.version == "1.2.3"
    assert v.to_string() == "None:library:name:1.2.3"

def test_from_string_missing_vendor_and_library():
    v = VLNV.from_string("name:1.2.3")
    assert v.vendor is None
    assert v.library is None
    assert v.name == "name"
    assert v.version == "1.2.3"
    assert v.to_string() == "None:None:name:1.2.3"

def test_from_string_only_version():
    v = VLNV.from_string("1.2.3")
    assert v.vendor is None
    assert v.library is None
    assert v.name is None
    assert v.version == "1.2.3"
    assert v.to_string() == "None:None:None:1.2.3"

def test_to_string_and_str_repr():
    v = VLNV("v", "l", "n", "1.0.0")
    assert v.to_string() == "v:l:n:1.0.0"
    assert str(v) == "v:l:n:1.0.0"
    assert repr(v) == "v:l:n:1.0.0"

def test_from_string_with_extra_colons():
    # Only splits on first 3 colons, rest stay in version
    v = VLNV.from_string("v:l:n:1.0.0-beta:extra")
    # This will assign as: vendor='v', library='l', name='n', version='1.0.0-beta:extra'
    assert v.vendor == "v"
    assert v.library == "l"
    assert v.name == "n"
    assert v.version == "1.0.0-beta:extra"
    assert v.to_string() == "v:l:n:1.0.0-beta:extra"
