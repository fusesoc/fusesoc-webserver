import io
import os
import stat
from unittest import mock
import pytest

from django.core.management import call_command
from django.db import IntegrityError
from github import GithubException
from git.exc import GitCommandError

from core_directory.models import Vendor, Library, Project, CorePackage


# Path to the management command module
COMMAND_PATH = "core_directory.management.commands.init_db"

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
        core_url="https://example.com/core",
        description="desc"
    )
    # Now run the command as before...
    import io
    from django.core.management import call_command
    out = io.StringIO()
    call_command("init_db", stdout=out)
    assert "Database already initialized." in out.getvalue()

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Command.download_and_load_data")
def test_command_runs_download_if_db_empty(mock_download):
    out = io.StringIO()
    call_command("init_db", stdout=out)
    assert "Database is empty. Initializing with data..." in out.getvalue()
    assert mock_download.called
    assert "Database initialized successfully." in out.getvalue()

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Github")
def test_get_repo_info_env_missing(mock_github):
    from core_directory.management.commands.init_db import Command
    cmd = Command()
    # Remove env vars
    with mock.patch.dict(os.environ, {}, clear=True):
        repo, token, branch = cmd.get_repo_info()
        assert repo is None and token is None and branch is None

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Github")
def test_get_repo_info_success(mock_github):
    from core_directory.management.commands.init_db import Command
    cmd = Command()
    # Set env vars
    with mock.patch.dict(os.environ, {"GITHUB_REPO": "user/repo", "GITHUB_ACCESS_TOKEN": "token"}):
        mock_repo = mock.Mock()
        mock_repo.default_branch = "main"
        mock_github.return_value.get_repo.return_value = mock_repo
        repo, token, branch = cmd.get_repo_info()
        assert repo == "user/repo"
        assert token == "token"
        assert branch == "main"

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Repo.clone_from")
@mock.patch(f"{COMMAND_PATH}.Command.get_repo_info")
@mock.patch(f"{COMMAND_PATH}.CoreSerializer")
def test_download_and_load_data_success(mock_serializer, mock_get_repo_info, mock_clone_from, tmp_path):
    from core_directory.management.commands.init_db import Command
    # Setup repo info
    mock_get_repo_info.return_value = ("user/repo", "token", "main")
    # Create dummy files in temp dir
    temp_dir = tmp_path
    core_file = temp_dir / "test.core"
    core_file.write_bytes(b"dummy core content")
    sig_file = temp_dir / "test.sig"
    sig_file.write_bytes(b"dummy sig content")
    # Patch os.listdir to return our files
    with mock.patch("os.listdir", return_value=["test.core", "test.sig"]), \
         mock.patch("tempfile.mkdtemp", return_value=str(temp_dir)), \
         mock.patch("shutil.rmtree"):
        cmd = Command()
        # Mock serializer
        instance = mock_serializer.return_value
        instance.is_valid.return_value = True
        instance.save.return_value = None
        cmd.stdout = io.StringIO()
        cmd.download_and_load_data()
        assert "Processing test.core" in cmd.stdout.getvalue()
        assert instance.is_valid.called
        assert instance.save.called

@mock.patch(f"{COMMAND_PATH}.Repo.clone_from", side_effect=GitCommandError('clone', 1))
@mock.patch(f"{COMMAND_PATH}.Command.get_repo_info")
def test_download_and_load_data_clone_error(mock_get_repo_info, mock_clone_from, tmp_path):
    from core_directory.management.commands.init_db import Command
    mock_get_repo_info.return_value = ("user/repo", "token", "main")
    with mock.patch("tempfile.mkdtemp", return_value=str(tmp_path)), \
         mock.patch("shutil.rmtree"):
        cmd = Command()
        cmd.stdout = io.StringIO()
        cmd.download_and_load_data()
        assert "error cloning repository" in cmd.stdout.getvalue().lower()


@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Repo.clone_from")
@mock.patch(f"{COMMAND_PATH}.Command.get_repo_info")
@mock.patch(f"{COMMAND_PATH}.CoreSerializer")
def test_download_and_load_data_with_signature(
    mock_serializer, mock_get_repo_info, mock_clone_from, tmp_path
):
    from core_directory.management.commands.init_db import Command

    # Setup repo info
    mock_get_repo_info.return_value = ("user/repo", "token", "main")

    # Create dummy files in temp dir
    temp_dir = tmp_path
    core_file = temp_dir / "test.core"
    core_file.write_bytes(b"dummy core content")
    sig_file = temp_dir / "test.core.sig"
    sig_file.write_bytes(b"dummy sig content")

    # Patch os.listdir to return our files
    with mock.patch("os.listdir", return_value=["test.core", "test.core.sig"]), \
         mock.patch("tempfile.mkdtemp", return_value=str(temp_dir)), \
         mock.patch("shutil.rmtree"):
        cmd = Command()
        # Mock serializer
        instance = mock_serializer.return_value
        instance.is_valid.return_value = True
        instance.save.return_value = None
        cmd.stdout = io.StringIO()
        cmd.download_and_load_data()

        # Check that the serializer was called with both core_file and sig_file
        called_data = mock_serializer.call_args[1]["data"]
        assert "core_file" in called_data
        assert "sig_file" in called_data
        assert called_data["sig_file"].name == "test.core.sig"
        assert called_data["sig_url"].endswith("test.core.sig")
        assert "Processing test.core" in cmd.stdout.getvalue()
        assert instance.is_valid.called
        assert instance.save.called

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Command.get_repo_info")
def test_download_and_load_data_returns_early_if_no_repo(mock_get_repo_info, tmp_path):
    from core_directory.management.commands.init_db import Command
    # Simulate get_repo_info returning (None, None, None)
    mock_get_repo_info.return_value = (None, None, None)
    with mock.patch("tempfile.mkdtemp", return_value=str(tmp_path)), \
         mock.patch("shutil.rmtree"):
        cmd = Command()
        cmd.stdout = io.StringIO()
        # Should return early, not attempt to clone or process files
        cmd.download_and_load_data()
        # Optionally, check that nothing was processed
        output = cmd.stdout.getvalue()
        # There should be no "Processing" or "Cloning" messages
        assert "Processing" not in output
        assert "Cloning" not in output

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Repo.clone_from", side_effect=OSError("filesystem error"))
@mock.patch(f"{COMMAND_PATH}.Command.get_repo_info")
def test_download_and_load_data_oserror(mock_get_repo_info, mock_clone_from, tmp_path):
    from core_directory.management.commands.init_db import Command
    mock_get_repo_info.return_value = ("user/repo", "token", "main")
    with mock.patch("tempfile.mkdtemp", return_value=str(tmp_path)), \
         mock.patch("shutil.rmtree"):
        cmd = Command()
        cmd.stdout = io.StringIO()
        cmd.download_and_load_data()
        output = cmd.stdout.getvalue().lower()
        assert "filesystem error cloning repository" in output

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Repo.clone_from")
@mock.patch(f"{COMMAND_PATH}.Command.get_repo_info")
@mock.patch(f"{COMMAND_PATH}.CoreSerializer")
def test_download_and_load_data_invalid_serializer(
    mock_serializer, mock_get_repo_info, mock_clone_from, tmp_path
):
    from core_directory.management.commands.init_db import Command

    mock_get_repo_info.return_value = ("user/repo", "token", "main")
    temp_dir = tmp_path
    core_file = temp_dir / "test.core"
    core_file.write_bytes(b"dummy core content")

    with mock.patch("os.listdir", return_value=["test.core"]), \
         mock.patch("tempfile.mkdtemp", return_value=str(temp_dir)), \
         mock.patch("shutil.rmtree"):
        cmd = Command()
        instance = mock_serializer.return_value
        instance.is_valid.return_value = False
        instance.errors = {"field": ["error"]}
        cmd.stdout = io.StringIO()
        cmd.download_and_load_data()
        output = cmd.stdout.getvalue().lower()
        assert "errors in test.core" in output
        assert "error" in output

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Repo.clone_from")
@mock.patch(f"{COMMAND_PATH}.Command.get_repo_info")
@mock.patch(f"{COMMAND_PATH}.CoreSerializer")
def test_download_and_load_data_save_exception(
    mock_serializer, mock_get_repo_info, mock_clone_from, tmp_path
):
    from core_directory.management.commands.init_db import Command

    mock_get_repo_info.return_value = ("user/repo", "token", "main")
    temp_dir = tmp_path
    core_file = temp_dir / "test.core"
    core_file.write_bytes(b"dummy core content")

    with mock.patch("os.listdir", return_value=["test.core"]), \
         mock.patch("tempfile.mkdtemp", return_value=str(temp_dir)), \
         mock.patch("shutil.rmtree"):
        cmd = Command()
        instance = mock_serializer.return_value
        instance.is_valid.return_value = True
        instance.save.side_effect = IntegrityError("save failed")
        cmd.stdout = io.StringIO()
        cmd.download_and_load_data()
        output = cmd.stdout.getvalue().lower()
        assert "error creating database object for test.core" in output
        assert "save failed" in output

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Github")
def test_get_repo_info_no_access_token(mock_github):
    from core_directory.management.commands.init_db import Command
    cmd = Command()
    # Set only GITHUB_REPO, not GITHUB_ACCESS_TOKEN
    with mock.patch.dict(os.environ, {"GITHUB_REPO": "user/repo"}, clear=True):
        repo, token, branch = cmd.get_repo_info()
        assert repo is None and token is None and branch is None

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Github")
def test_get_repo_info_github_exception(mock_github):
    from core_directory.management.commands.init_db import Command
    cmd = Command()
    # Set both env vars
    with mock.patch.dict(os.environ, {"GITHUB_REPO": "user/repo", "GITHUB_ACCESS_TOKEN": "token"}, clear=True):
        # Simulate GithubException when calling get_repo
        mock_github.return_value.get_repo.side_effect = GithubException(500, "fail", None)
        repo, token, branch = cmd.get_repo_info()
        assert repo is None and token is None and branch is None

@pytest.mark.django_db
@mock.patch(f"{COMMAND_PATH}.Github")
def test_get_repo_info_attribute_error(mock_github):
    from core_directory.management.commands.init_db import Command
    cmd = Command()
    # Set both env vars
    with mock.patch.dict(os.environ, {"GITHUB_REPO": "user/repo", "GITHUB_ACCESS_TOKEN": "token"}, clear=True):
        # Simulate AttributeError when calling get_repo
        mock_github.return_value.get_repo.side_effect = AttributeError("fail")
        repo, token, branch = cmd.get_repo_info()
        assert repo is None and token is None and branch is None

def test_on_rm_exc_makes_file_writable_and_retries(tmp_path):
    from core_directory.management.commands.init_db import Command

    file_path = tmp_path / "dummy.txt"
    file_path.write_text("test")
    file_path.chmod(0o400)

    called = {}

    # Instead of actually removing, just record the call
    def fake_remove(path):
        called["called"] = True
        # Simulate successful removal (do nothing)

    with mock.patch("os.chmod") as mock_chmod, \
         mock.patch("os.access", return_value=False):
        Command._on_rm_exc(fake_remove, str(file_path), (PermissionError, PermissionError("denied"), None))
        mock_chmod.assert_called_with(str(file_path), stat.S_IWUSR)
        assert called["called"]

def test_on_rm_exc_raises_other_errors(tmp_path):
    from core_directory.management.commands.init_db import Command

    file_path = tmp_path / "dummy.txt"
    file_path.write_text("test")

    with mock.patch("os.access", return_value=True):
        with pytest.raises(PermissionError):
            Command._on_rm_exc(lambda p: None, str(file_path), (PermissionError, PermissionError("denied"), None))
