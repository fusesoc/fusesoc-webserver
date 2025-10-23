import io
import os
import pytest
from unittest import mock

from django.core.files.base import ContentFile

from core_directory.storages.github import GitHubStorage
from github import UnknownObjectException, GithubException

@pytest.fixture
def mock_github(monkeypatch):
    # Patch Github and repo
    mock_repo = mock.Mock()
    mock_github = mock.Mock()
    mock_github.get_repo.return_value = mock_repo
    monkeypatch.setattr("core_directory.storages.github.Github", lambda **kwargs: mock_github)
    monkeypatch.setattr("core_directory.storages.github.GitHubAuthToken", lambda token: token)
    return mock_repo

@pytest.fixture
def storage(mock_github, tmp_path, monkeypatch):
    # Patch os.makedirs to avoid real dirs
    monkeypatch.setattr(os, "makedirs", lambda *a, **k: None)
    # Use a temp cache dir
    return GitHubStorage(
        repo_name="user/repo",
        access_token="token",
        branch="main",
        cache_dir=str(tmp_path)
    )

def test_init_env_vars(monkeypatch):
    monkeypatch.setenv("GITHUB_REPO", "user/repo")
    monkeypatch.setenv("GITHUB_ACCESS_TOKEN", "token")
    monkeypatch.setenv("GITHUB_BRANCH", "main")
    monkeypatch.setenv("GITHUB_STORAGE_CACHE_DIR", "/tmp/cache")
    with mock.patch("core_directory.storages.github.Github") as mock_github, \
         mock.patch("core_directory.storages.github.GitHubAuthToken"):
        storage = GitHubStorage()
        assert storage.repo_name == "user/repo"
        assert storage.access_token == "token"
        assert storage.branch == "main"
        assert storage.cache_dir == "/tmp/cache"

def test_init_raises_if_no_repo_or_token(monkeypatch):
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    monkeypatch.delenv("GITHUB_ACCESS_TOKEN", raising=False)
    with pytest.raises(ValueError):
        GitHubStorage(repo_name=None, access_token=None)

def test_init_makes_cache_dir(monkeypatch):
    # Patch Github and GitHubAuthToken to avoid real network
    monkeypatch.setattr("core_directory.storages.github.Github", lambda **kwargs: mock.Mock(get_repo=lambda repo_name: mock.Mock()))
    monkeypatch.setattr("core_directory.storages.github.GitHubAuthToken", lambda token: token)

    called = {}
    def fake_makedirs(path, exist_ok):
        called["path"] = path
        called["exist_ok"] = exist_ok
    monkeypatch.setattr("os.makedirs", fake_makedirs)
    GitHubStorage(repo_name="r", access_token="t", cache_dir="/tmp/mycache")
    assert called["path"] == "/tmp/mycache"
    assert called["exist_ok"] is True

def test_open_reads_from_cache(storage, tmp_path, monkeypatch):
    # Write a file to cache
    cache_file = tmp_path / "foo.txt"
    cache_file.write_bytes(b"hello")
    result = storage._open("foo.txt")
    assert result.read() == b"hello"
    assert result.name == "foo.txt"

def test_open_reads_from_github(storage, mock_github, tmp_path, monkeypatch):
    # Remove cache file
    cache_file = tmp_path / "bar.txt"
    if cache_file.exists():
        cache_file.unlink()
    # Mock repo.get_contents
    mock_file = mock.Mock()
    mock_file.decoded_content = b"from github"
    mock_github.get_contents.return_value = mock_file
    result = storage._open("bar.txt")
    assert result.read() == b"from github"
    assert result.name == "bar.txt"
    # Should write to cache
    assert (tmp_path / "bar.txt").exists()

def test_open_file_not_found(storage, mock_github):
    mock_github.get_contents.side_effect = UnknownObjectException(404, "Not found", None)
    with pytest.raises(FileNotFoundError):
        storage._open("missing.txt")

def test_open_github_exception(storage, mock_github):
    mock_github.get_contents.side_effect = GithubException(500, "fail", None)
    with pytest.raises(IOError):
        storage._open("fail.txt")

def test_save_creates_file(storage, mock_github, tmp_path):
    # Simulate file does not exist
    mock_github.get_contents.side_effect = UnknownObjectException(404, "Not found", None)
    content = ContentFile(b"abc", name="foo.txt")
    storage._repo.create_file.return_value = None
    result = storage._save("foo.txt", content)
    assert result == "foo.txt"
    storage._repo.create_file.assert_called_once()
    # Should write to cache
    assert (tmp_path / "foo.txt").exists()

def test_save_updates_file(storage, mock_github, tmp_path):
    # Simulate file exists
    mock_file = mock.Mock()
    mock_file.sha = "sha123"
    mock_github.get_contents.return_value = mock_file
    content = ContentFile(b"def", name="foo.txt")
    storage._repo.update_file.return_value = None
    result = storage._save("foo.txt", content)
    assert result == "foo.txt"
    storage._repo.update_file.assert_called_once()
    # Should write to cache
    assert (tmp_path / "foo.txt").exists()

def test_save_github_exception(storage, mock_github):
    mock_github.get_contents.side_effect = GithubException(500, "fail", None)
    content = ContentFile(b"abc", name="foo.txt")
    with pytest.raises(IOError):
        storage._save("foo.txt", content)

def test_delete_removes_file(storage, mock_github, tmp_path):
    # Simulate file exists
    mock_file = mock.Mock()
    mock_file.sha = "sha123"
    mock_github.get_contents.return_value = mock_file
    storage._repo.delete_file.return_value = None
    # Write to cache
    cache_file = tmp_path / "foo.txt"
    cache_file.write_bytes(b"abc")
    storage.delete("foo.txt")
    storage._repo.delete_file.assert_called_once()
    assert not cache_file.exists()

def test_delete_file_not_found(storage, mock_github, tmp_path):
    # Simulate file does not exist
    mock_github.get_contents.side_effect = UnknownObjectException(404, "Not found", None)
    # Write to cache
    cache_file = tmp_path / "foo.txt"
    cache_file.write_bytes(b"abc")
    storage.delete("foo.txt")
    # Should remove cache file
    assert not cache_file.exists()

def test_delete_github_exception(storage, mock_github):
    mock_github.get_contents.side_effect = GithubException(500, "fail", None)
    with pytest.raises(IOError):
        storage.delete("foo.txt")

def test_exists_checks_cache_and_github(storage, mock_github, tmp_path):
    # File in cache
    cache_file = tmp_path / "foo.txt"
    cache_file.write_bytes(b"abc")
    assert storage.exists("foo.txt")
    # Not in cache, but in github
    cache_file.unlink()
    mock_github.get_contents.return_value = mock.Mock()
    assert storage.exists("foo.txt")
    # Not in cache, not in github
    mock_github.get_contents.side_effect = UnknownObjectException(404, "Not found", None)
    assert not storage.exists("foo.txt")

def test_get_available_name_calls_delete(storage, monkeypatch):
    called = {}
    def fake_delete(name):
        called["deleted"] = name
        return None
    monkeypatch.setattr(storage, "delete", fake_delete)
    name = storage.get_available_name("foo.txt")
    assert name == "foo.txt"
    assert called["deleted"] == "foo.txt"

def test_url(storage):
    url = storage.url("foo.txt")
    assert url == "https://raw.githubusercontent.com/user/repo/main/foo.txt"

def test_size_returns_size(storage, mock_github):
    mock_file = mock.Mock()
    mock_file.size = 123
    mock_github.get_contents.return_value = mock_file
    assert storage.size("foo.txt") == 123

def test_size_returns_zero_if_not_found(storage, mock_github):
    mock_github.get_contents.side_effect = UnknownObjectException(404, "Not found", None)
    assert storage.size("foo.txt") == 0

def test_listdir(storage, mock_github):
    file1 = mock.Mock()
    file1.name = "foo.txt"
    file1.type = "file"
    dir1 = mock.Mock()
    dir1.name = "bar"
    dir1.type = "dir"
    mock_github.get_contents.return_value = [file1, dir1]
    dirs, files = storage.listdir("")
    assert dirs == ["bar"]
    assert files == ["foo.txt"]

def test_listdir_not_implemented(storage):
    with pytest.raises(NotImplementedError):
        storage.listdir("not-root")

def test_listdir_not_root_raises(monkeypatch):
    # Patch Github and GitHubAuthToken to avoid real network
    monkeypatch.setattr("core_directory.storages.github.Github", lambda **kwargs: mock.Mock(get_repo=lambda repo_name: mock.Mock()))
    monkeypatch.setattr("core_directory.storages.github.GitHubAuthToken", lambda token: token)
    storage = GitHubStorage(repo_name="r", access_token="t")
    with pytest.raises(NotImplementedError):
        storage.listdir("not-root")

def test_clear_cache(tmp_path, monkeypatch):
    # Patch Github and GitHubAuthToken to avoid real network
    monkeypatch.setattr("core_directory.storages.github.Github", lambda **kwargs: mock.Mock(get_repo=lambda repo_name: mock.Mock()))
    monkeypatch.setattr("core_directory.storages.github.GitHubAuthToken", lambda token: token)

    # Create files and dirs in cache
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "file1.txt").write_text("abc")
    (cache_dir / "dir1").mkdir()
    (cache_dir / "dir1" / "file2.txt").write_text("def")
    storage = GitHubStorage(
        repo_name="user/repo",
        access_token="token",
        branch="main",
        cache_dir=str(cache_dir)
    )
    storage.clear_cache()
    assert not any(cache_dir.iterdir())

def test_prefill_cache_success(monkeypatch, tmp_path):
    # Patch Github and GitHubAuthToken to avoid real network
    monkeypatch.setattr("core_directory.storages.github.Github", lambda **kwargs: mock.Mock(get_repo=lambda repo_name: mock.Mock()))
    monkeypatch.setattr("core_directory.storages.github.GitHubAuthToken", lambda token: token)

    # Patch requests.get, zipfile.ZipFile, etc.
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    storage = GitHubStorage(
        repo_name="user/repo",
        access_token="token",
        branch="main",
        cache_dir=str(cache_dir)
    )
    # Patch clear_cache
    storage.clear_cache = mock.Mock()
    # Patch requests.get
    fake_response = mock.Mock()
    fake_response.status_code = 200
    fake_response.iter_content = lambda chunk_size: [b"zipdata"]
    monkeypatch.setattr("core_directory.storages.github.requests.get", lambda *a, **k: fake_response)
    # Patch zipfile.ZipFile
    class FakeZip:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def extractall(self, path):
            # Create a fake extracted dir and file
            extracted_dir = os.path.join(path, "repo-main")
            os.makedirs(extracted_dir, exist_ok=True)
            with open(os.path.join(extracted_dir, "foo.txt"), "wb") as f:
                f.write(b"abc")
    monkeypatch.setattr("core_directory.storages.github.zipfile.ZipFile", lambda *a, **k: FakeZip())
    # Patch os.listdir to simulate extracted dir
    def fake_listdir(path):
        if "repo-main" in path:
            return ["foo.txt"]
        if os.path.basename(path).startswith("tmp"):
            return ["repo-main"]
        return []
    monkeypatch.setattr("os.listdir", fake_listdir)
    # Patch os.path.isdir to match our fake structure
    monkeypatch.setattr("os.path.isdir", lambda path: "repo-main" in path or "cache" in path)
    storage.prefill_cache()
    # Should have file in cache
    assert (cache_dir / "foo.txt").exists()
    
def test_prefill_cache_no_cache_dir(monkeypatch):
    monkeypatch.setattr("core_directory.storages.github.Github", lambda **kwargs: mock.Mock(get_repo=lambda repo_name: mock.Mock()))
    monkeypatch.setattr("core_directory.storages.github.GitHubAuthToken", lambda token: token)
    storage = GitHubStorage(repo_name="r", access_token="t", cache_dir=None)
    with pytest.raises(RuntimeError):
        storage.prefill_cache()

def test_prefill_cache_bad_status(monkeypatch, tmp_path):
    monkeypatch.setattr("core_directory.storages.github.Github", lambda **kwargs: mock.Mock(get_repo=lambda repo_name: mock.Mock()))
    monkeypatch.setattr("core_directory.storages.github.GitHubAuthToken", lambda token: token)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    storage = GitHubStorage(repo_name="r", access_token="t", cache_dir=str(cache_dir))
    storage.clear_cache = mock.Mock()
    fake_response = mock.Mock()
    fake_response.status_code = 404
    fake_response.text = "not found"
    monkeypatch.setattr("core_directory.storages.github.requests.get", lambda *a, **k: fake_response)
    with pytest.raises(RuntimeError) as excinfo:
        storage.prefill_cache()
    assert "Failed to download repo archive" in str(excinfo.value)

def test_prefill_cache_no_extracted_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("core_directory.storages.github.Github", lambda **kwargs: mock.Mock(get_repo=lambda repo_name: mock.Mock()))
    monkeypatch.setattr("core_directory.storages.github.GitHubAuthToken", lambda token: token)
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    storage = GitHubStorage(repo_name="r", access_token="t", cache_dir=str(cache_dir))
    storage.clear_cache = mock.Mock()
    fake_response = mock.Mock()
    fake_response.status_code = 200
    fake_response.iter_content = lambda chunk_size: [b"zipdata"]
    monkeypatch.setattr("core_directory.storages.github.requests.get", lambda *a, **k: fake_response)
    class FakeZip:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def extractall(self, path): pass  # Do not create any dirs
    monkeypatch.setattr("core_directory.storages.github.zipfile.ZipFile", lambda *a, **k: FakeZip())
    # Patch os.listdir to always return empty list for temp_dir
    monkeypatch.setattr("os.listdir", lambda path: [])
    with pytest.raises(RuntimeError) as excinfo:
        storage.prefill_cache()
    assert "No directory found in extracted archive" in str(excinfo.value)
    