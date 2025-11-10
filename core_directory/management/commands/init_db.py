"""
Provides a Django management command to initialize the database with GitHub repository data if empty.
Clones the repository locally using a GitHub access token, processes files in the root directory,
and stores both local file content and GitHub URLs in the database using a serializer.
Utilizes environment variables for configuration.
"""
from django.db import IntegrityError
from django.core.exceptions import ValidationError as DjangoValidationError

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage

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
            self.initialize_from_storage()
            self.stdout.write(self.style.SUCCESS('Database initialized successfully.'))
        else:
            self.stdout.write(self.style.WARNING('Database already initialized.'))

    def initialize_from_storage(self):
        """
        Loads core and signature files from the configured backend storage into the database.
        """
        storage = default_storage

        # Prefill cache if supported
        prefill = getattr(storage, "prefill_cache", None)
        if callable(prefill):
            self.stdout.write('Prefilling storage cache...')
            try:
                prefill()
                self.stdout.write(self.style.SUCCESS('Cache prefilled.'))
            except RuntimeError as e:
                self.stdout.write(self.style.ERROR(f'Error during cache prefill: {e}'))

        _, files_in_root = storage.listdir('')
        core_files = [f for f in files_in_root if f.endswith('.core')]
        sig_files = {f.removesuffix('.sig'): f for f in files_in_root if f.endswith('.sig')}

        for core_filename in core_files:
            self.stdout.write(f'Processing {core_filename}...')

            with storage.open(core_filename, 'rb') as f:
                core_file_object = ContentFile(f.read())
                core_file_object.name = core_filename
                core_file_object.size = core_file_object.size

            data = {
                'core_file': core_file_object,
            }

            # Attach signature file if present
            if core_filename in sig_files:
                sig_filename = sig_files[core_filename]
                with storage.open(sig_filename, 'rb') as f:
                    sig_file_object = ContentFile(f.read())
                    sig_file_object.name = sig_filename
                    sig_file_object.size = sig_file_object.size
                data['signature_file'] = sig_file_object

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
