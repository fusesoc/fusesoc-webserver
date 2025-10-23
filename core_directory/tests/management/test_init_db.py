import io
from unittest import mock
import pytest

from django.db import IntegrityError
from django.core.files.base import ContentFile
from django.core.management import call_command

from core_directory.management.commands.init_db import Command
from core_directory.models import Vendor, Library, Project, CorePackage

# Path to the management command module
COMMAND_PATH = "core_directory.management.commands.init_db"

@pytest.fixture
def fake_storage():
    storage = mock.Mock()
    # Simulate two files: one core, one sig
    storage.listdir.return_value = ([], ["foo.core", "foo.core.sig", "bar.core"])
    storage.url.side_effect = lambda name: f"https://example.com/{name}"
    # Simulate file content
    def fake_open(name, mode='rb'):
        f = ContentFile(b"dummy content")
        f.name = name
        f.size = len(f.read())
        f.seek(0)
        return f
    storage.open.side_effect = fake_open
    return storage


@pytest.mark.django_db
def test_command_skips_if_db_not_empty():
    # Create all required related objects
    vendor = Vendor.objects.create(name="Acme")
    library = Library.objects.create(vendor=vendor, name="Lib1")
    project = Project.objects.create(vendor=vendor, library=library, name="Core1", description="desc")
    CorePackage.objects.create(
        project=project,
        vlnv_name="dummy:dummy:dummy:1.0.0",
        version="1.0.0",
        core_file="dummy.core",
        description="desc"
    )
    # Now run the command as before...
    import io
    from django.core.management import call_command
    out = io.StringIO()
    call_command("init_db", stdout=out)
    assert "Database already initialized." in out.getvalue()

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Command.initialize_from_storage")
def test_command_runs_download_if_db_empty(mock_download):
    out = io.StringIO()
    call_command("init_db", stdout=out)
    assert "Database is empty. Initializing with data..." in out.getvalue()
    assert mock_download.called
    assert "Database initialized successfully." in out.getvalue()

@pytest.mark.django_db
def test_initialize_from_storage_prefill_and_success(monkeypatch, fake_storage):
    cmd = Command()
    cmd.stdout = io.StringIO()

    # Patch GitHubStorage to return our fake storage
    monkeypatch.setattr("core_directory.management.commands.init_db.GitHubStorage", lambda: fake_storage)
    # Add a prefill_cache method
    fake_storage.prefill_cache = mock.Mock()

    # Patch CoreSerializer
    fake_serializer = mock.Mock()
    fake_serializer.is_valid.return_value = True
    fake_serializer.save.return_value = None
    monkeypatch.setattr("core_directory.management.commands.init_db.CoreSerializer", lambda data: fake_serializer)

    cmd.initialize_from_storage()

    # Check prefill_cache was called
    fake_storage.prefill_cache.assert_called_once()
    # Should process both core files
    assert "Processing foo.core" in cmd.stdout.getvalue()
    assert "Processing bar.core" in cmd.stdout.getvalue()
    # Should call serializer.save() for each core file
    assert fake_serializer.save.call_count == 2

@pytest.mark.django_db
def test_initialize_from_storage_prefill_error(monkeypatch, fake_storage):
    cmd = Command()
    cmd.stdout = io.StringIO()

    monkeypatch.setattr("core_directory.management.commands.init_db.GitHubStorage", lambda: fake_storage)
    # Simulate prefill_cache raising RuntimeError
    fake_storage.prefill_cache = mock.Mock(side_effect=RuntimeError("fail prefill"))

    fake_serializer = mock.Mock()
    fake_serializer.is_valid.return_value = True
    fake_serializer.save.return_value = None
    monkeypatch.setattr("core_directory.management.commands.init_db.CoreSerializer", lambda data: fake_serializer)

    cmd.initialize_from_storage()
    assert "Error during cache prefill: fail prefill" in cmd.stdout.getvalue()

@pytest.mark.django_db
def test_initialize_from_storage_serializer_invalid(monkeypatch, fake_storage):
    cmd = Command()
    cmd.stdout = io.StringIO()

    monkeypatch.setattr("core_directory.management.commands.init_db.GitHubStorage", lambda: fake_storage)
    fake_storage.prefill_cache = mock.Mock()

    fake_serializer = mock.Mock()
    fake_serializer.is_valid.return_value = False
    fake_serializer.errors = {"core_file": ["invalid"]}
    monkeypatch.setattr("core_directory.management.commands.init_db.CoreSerializer", lambda data: fake_serializer)

    cmd.initialize_from_storage()
    assert "Errors in foo.core" in cmd.stdout.getvalue()
    assert "invalid" in cmd.stdout.getvalue()

@pytest.mark.django_db
def test_initialize_from_storage_save_exception(monkeypatch, fake_storage):
    cmd = Command()
    cmd.stdout = io.StringIO()

    monkeypatch.setattr("core_directory.management.commands.init_db.GitHubStorage", lambda: fake_storage)
    fake_storage.prefill_cache = mock.Mock()

    fake_serializer = mock.Mock()
    fake_serializer.is_valid.return_value = True
    fake_serializer.save.side_effect = IntegrityError("save failed")

    monkeypatch.setattr("core_directory.management.commands.init_db.CoreSerializer", lambda data: fake_serializer)

    cmd.initialize_from_storage()
    assert "Error creating database object for foo.core" in cmd.stdout.getvalue()
    assert "save failed" in cmd.stdout.getvalue()