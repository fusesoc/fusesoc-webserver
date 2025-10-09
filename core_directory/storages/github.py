"""
Django storage backend for GitHub repositories.

This module provides a Django Storage class that stores files in a GitHub repository,
with optional local caching for efficient repeated access. It supports overwriting files,
deleting files, and retrieving direct raw URLs. The storage backend is fully compatible
with Django's standard storage API, making it interchangeable with other backends.

Configuration is via environment variables or constructor arguments:
    - GITHUB_REPO: GitHub repository in 'owner/repo' format
    - GITHUB_ACCESS_TOKEN: Personal access token with repo access
    - GITHUB_BRANCH: Branch to use (default: 'main')
    - GITHUB_STORAGE_CACHE_DIR: Optional local cache directory

Example usage:
    from core_directory.storage import GitHubStorage
    storage = GitHubStorage()
    storage.save('foo.txt', ContentFile(b'hello'))
    with storage.open('foo.txt') as f:
        print(f.read())
    storage.delete('foo.txt')
"""

import requests
import zipfile
import shutil
import tempfile
import os

from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from github import Github, GithubException, UnknownObjectException
from github.Auth import Token as GitHubAuthToken

class GitHubStorage(Storage):
    """
    Django storage backend for GitHub repository files, with overwrite and optional local caching.
    Implements only the standard Django storage API methods.
    """

    def __init__(self, repo_name=None, access_token=None, branch=None, cache_dir=None):
        self.repo_name = repo_name or os.getenv('GITHUB_REPO')
        self.access_token = access_token or os.getenv('GITHUB_ACCESS_TOKEN')
        self.branch = branch or os.getenv('GITHUB_BRANCH', 'main')
        self.cache_dir = cache_dir or os.getenv('GITHUB_STORAGE_CACHE_DIR')
        if not self.repo_name or not self.access_token:
            raise ValueError("GITHUB_REPO and GITHUB_ACCESS_TOKEN must be set")
        self._github = Github(auth=GitHubAuthToken(self.access_token))
        self._repo = self._github.get_repo(self.repo_name)
        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_path(self, name):
        if not self.cache_dir:
            return None
        return os.path.join(self.cache_dir, name)

    def _open(self, name, mode='rb'):
        """
        Retrieve file content from cache if available, else from GitHub and cache it.
        """
        cache_path = self._cache_path(name)
        if cache_path and os.path.exists(cache_path):
            with open(cache_path, 'rb') as f:
                return ContentFile(f.read(), name=name)
        try:
            file_content = self._repo.get_contents(name, ref=self.branch)
            content = file_content.decoded_content
            if cache_path:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, 'wb') as f:
                    f.write(content)
            return ContentFile(content, name=name)
        except UnknownObjectException:
            raise FileNotFoundError(f"{name} not found in GitHub repo")
        except GithubException as e:
            raise IOError(f"GitHub error: {e}")

    def _save(self, name, content):
        """
        Save or overwrite a file in the GitHub repo.
        If the file exists, it is updated; otherwise, it is created.
        """
        content.seek(0)
        data = content.read()
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        try:
            # Try to get the file (to update)
            file_content = self._repo.get_contents(name, ref=self.branch)
            self._repo.update_file(
                name,
                f"Update {name} via Django storage",
                data,
                file_content.sha,
                branch=self.branch
            )
        except UnknownObjectException:
            # File does not exist, create it
            self._repo.create_file(
                name,
                f"Add {name} via Django storage",
                data,
                branch=self.branch
            )
        except GithubException as e:
            raise IOError(f"GitHub error: {e}")

        # Optionally update cache
        cache_path = self._cache_path(name)
        if cache_path:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, 'wb') as f:
                f.write(data.encode('utf-8'))
        return name

    def delete(self, name):
        """
        Delete a file from GitHub and remove it from the local cache if present.
        """
        try:
            file_content = self._repo.get_contents(name, ref=self.branch)
            self._repo.delete_file(
                name,
                f"Delete {name} via Django storage",
                file_content.sha,
                branch=self.branch
            )
        except UnknownObjectException:
            pass  # Already deleted
        except GithubException as e:
            raise IOError(f"GitHub error: {e}")

        # Invalidate cache
        cache_path = self._cache_path(name)
        if cache_path and os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except OSError:
                pass  # Ignore errors if file is already gone

    def exists(self, name):
        """
        Check if a file exists in the cache or on GitHub.
        """
        cache_path = self._cache_path(name)
        if cache_path and os.path.exists(cache_path):
            return True
        try:
            self._repo.get_contents(name, ref=self.branch)
            return True
        except UnknownObjectException:
            return False

    def url(self, name):
        """
        Return the direct raw URL for the file on GitHub.
        """
        return f"https://raw.githubusercontent.com/{self.repo_name}/{self.branch}/{name}"

    def size(self, name):
        """
        Return the size of the file in bytes.
        """
        try:
            file_content = self._repo.get_contents(name, ref=self.branch)
            return file_content.size
        except UnknownObjectException:
            return 0

    def listdir(self, path):
        """
        List files and directories in the given path (only root supported).
        """
        if path not in ('', '/'):
            raise NotImplementedError("Only root directory listing is supported")
        contents = self._repo.get_contents('', ref=self.branch)
        files = [c.name for c in contents if c.type == 'file']
        dirs = [c.name for c in contents if c.type == 'dir']
        return dirs, files
    
    def clear_cache(self):
        """
        Remove all files and subdirectories from the given cache directory.

        Use this to ensure the cache is empty before prefilling, so only current repo files are cached.
        """
        for filename in os.listdir(self.cache_dir):
            file_path = os.path.join(self.cache_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')
    
    def prefill_cache(self):
        """
        Download the GitHub repo as a zip and prefill the cache directory with its files.
        The cache is cleared first to remove any old or stale files.
        Only works if cache_dir is set.
        """      
        if not self.cache_dir:
            raise RuntimeError("No cache_dir set for GitHubStorage; cannot prefill cache.")

        self.clear_cache()

        zip_url = f"https://api.github.com/repos/{self.repo_name}/zipball/{self.branch}"
        headers = {'Authorization': f'token {self.access_token}'}
        response = requests.get(zip_url, headers=headers, stream=True)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download repo archive: {response.status_code} {response.text}")

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, 'repo.zip')
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                extracted_dirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
                if not extracted_dirs:
                    raise RuntimeError("No directory found in extracted archive.")
                repo_root = os.path.join(temp_dir, extracted_dirs[0])
                files_in_root = os.listdir(repo_root)
                for filename in files_in_root:
                    src_path = os.path.join(repo_root, filename)
                    if os.path.isfile(src_path):
                        cache_path = os.path.join(self.cache_dir, filename)
                        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                        with open(src_path, 'rb') as src, open(cache_path, 'wb') as dst:
                            dst.write(src.read())
    