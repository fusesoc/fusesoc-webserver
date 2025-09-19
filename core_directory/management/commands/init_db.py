"""
Provides a Django management command to initialize the database with GitHub repository data if empty.
Clones the repository locally using a GitHub access token, processes files in the root directory,
and stores both local file content and GitHub URLs in the database using a serializer.
Utilizes environment variables for configuration.
"""

import os
import tempfile
import shutil
import stat

from dataclasses import dataclass

from io import BytesIO
from git import Repo
from git.exc import GitCommandError

from github import Github, GithubException
from github.Auth import Token as GitHubAuthToken

from django.db import IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management.base import BaseCommand

from rest_framework.exceptions import ValidationError as DRFValidationError

from core_directory.serializers import CoreSerializer
from core_directory.models import CorePackage

class Command(BaseCommand):
    """
    Initializes the database from a specified GitHub repository when empty.

    Clones the GitHub repository locally using an access token, processes core and signature files
    in the root directory, and saves them to the database using CoreSerializer. Stores both the
    local file content and the corresponding GitHub URLs.

    Attributes:
        help (str): Brief description of the command.

    Methods:
        handle(*args, **kwargs): Checks if the database is empty and initiates data loading.
        get_repo_info(): Retrieves repository information and default branch using the GitHub API.
        download_and_load_data(): Clones the repository and processes files for database import.

    Environment Variables:
        GITHUB_ACCESS_TOKEN: GitHub API authentication token.
        GITHUB_REPO: Repository name in 'username/repo' format.

    Usage:
        Execute from the command line: `python manage.py <command_name>`

    Example:
        python manage.py init_db
    """
    help = 'Initializes the database with data from a GitHub repository if it is empty.'

    def handle(self, *args, **kwargs):
        """
        Checks if the database is empty and initiates data loading from the GitHub repository.
        """
        if not CorePackage.objects.exists():
            self.stdout.write(self.style.SUCCESS('Database is empty. Initializing with data...'))
            self.download_and_load_data()
            self.stdout.write(self.style.SUCCESS('Database initialized successfully.'))
        else:
            self.stdout.write(self.style.WARNING('Database already initialized.'))

    def get_repo_info(self):
        """
        Retrieves repository information and default branch using the GitHub API.

        Returns:
            tuple: (repo_name, access_token, default_branch) if successful, otherwise (None, None, None).
        """
        repo_name = os.getenv('GITHUB_REPO')
        access_token = os.getenv('GITHUB_ACCESS_TOKEN')
        if not repo_name:
            self.stdout.write(self.style.ERROR('GITHUB_REPO environment variable is not set.'))
            return None, None, None
        if not access_token:
            self.stdout.write(self.style.ERROR('GITHUB_ACCESS_TOKEN environment variable is not set.'))
            return None, None, None
        g = Github(auth=GitHubAuthToken(os.getenv('GITHUB_ACCESS_TOKEN')))
        try:
            repo = g.get_repo(repo_name)
            default_branch = repo.default_branch
            return repo_name, access_token, default_branch
        except GithubException as e:
            self.stdout.write(self.style.ERROR(f'GitHub API error fetching repo info: {e}'))
            return None, None, None
        except AttributeError as e:
            self.stdout.write(self.style.ERROR(f'Attribute error fetching repo info: {e}'))
            return None, None, None

    def download_and_load_data(self):
        """
        Clones the GitHub repo locally and loads .core and .sig files from the root directory into the database.

        Constructs GitHub URLs for each file and stores both the local file content and the GitHub URL
        in the database using the CoreSerializer.
        """
        @dataclass
        class RepositoryData:
            """
            Container for GitHub repository authentication and metadata.

            Attributes:
                name (str): The full repository name in 'owner/repo' format.
                access_token (str): The GitHub access token for authentication.
                default_branch (str): The default branch of the repository.

            Properties:
                url (str): The HTTPS URL of the repository.
                url_with_access_token (str): The HTTPS URL of the repository including the access token.
                base_url_raw_files (str): The base URL for downloading raw files from the repository's default branch.
            """
            name: str
            access_token: str
            default_branch: str

            @property
            def url(self):
                """Returns the URL of the repository."""
                return f"https://github.com/{self.name}.git"

            @property
            def url_with_access_token(self):
                """Returns the URL of the repository including access token."""
                return f"https://{self.access_token}@github.com/{self.name}.git"

            @property
            def base_url_raw_files(self):
                """Returns the base URL for raw file download from github."""
                return f"https://raw.githubusercontent.com/{self.name}/refs/heads/{self.default_branch}"

        repo = RepositoryData(*self.get_repo_info())
        if not repo.name:
            return

        temp_dir = tempfile.mkdtemp()
        self.stdout.write(f'Cloning repository {repo.url} to {temp_dir}...')
        try:
            Repo.clone_from(repo.url_with_access_token, temp_dir)
        except GitCommandError as e:
            self.stdout.write(self.style.ERROR(f'Git error cloning repository: {e}'))
            shutil.rmtree(temp_dir)
            return
        except OSError as e:
            self.stdout.write(self.style.ERROR(f'Filesystem error cloning repository: {e}'))
            shutil.rmtree(temp_dir)
            return

        # Only process files in the root directory
        files_in_root = os.listdir(temp_dir)
        core_files = [f for f in files_in_root if f.endswith('.core')]
        sig_files = {f.removesuffix('.sig'): f for f in files_in_root if f.endswith('.sig')}

        for core_filename in core_files:
            self.stdout.write(f'Processing {core_filename}...')

            with open(os.path.join(temp_dir, core_filename), 'rb') as f:
                core_file_object = BytesIO(f.read())
                core_file_object.name = core_filename
                core_file_object.size = core_file_object.getbuffer().nbytes

            data = {
                'core_file': core_file_object,
                'core_url': f"{repo.base_url_raw_files}/{core_filename}"
            }

            # Attach signature file if present
            if core_filename in sig_files:
                sig_filename = sig_files[core_filename]

                with open(os.path.join(temp_dir, sig_filename), 'rb') as f:
                    sig_file_object = BytesIO(f.read())
                    sig_file_object.name = sig_filename
                    sig_file_object.size = sig_file_object.getbuffer().nbytes
                data['sig_file'] = sig_file_object
                data['sig_url'] = f"{repo.base_url_raw_files}/{sig_filename}"

            # Use the serializer to create database entries
            serializer = CoreSerializer(data=data)
            if serializer.is_valid():
                try:
                    serializer.save()
                    self.stdout.write(self.style.SUCCESS(f'Data from {core_filename} loaded successfully.'))
                except (IntegrityError, DjangoValidationError, DRFValidationError) as e:
                    self.stdout.write(self.style.ERROR(f'Error creating database object for {core_filename}: {e}'))
            else:
                self.stdout.write(self.style.ERROR(f'Errors in {core_filename}: {serializer.errors}'))

        shutil.rmtree(temp_dir, onexc=self._on_rm_exc)

    @staticmethod
    def _on_rm_exc(func, path, excinfo):
        """
        Error handler for `shutil.rmtree` using the `onexc` parameter (Python 3.12+).

        If the removal failed, make the file writable and try again.
        """
        if not os.access(path, os.W_OK):
            os.chmod(path, stat.S_IWUSR)
            func(path)
        else:
            raise excinfo[1]
