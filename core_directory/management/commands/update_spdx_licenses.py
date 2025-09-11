"""
Management command to download and update the SPDX license list (licenses.json).

This command fetches the latest SPDX license list from the official SPDX website
and saves it to the location specified in Django settings (SPDX_LICENSES_PATH).
Keeping this file up to date ensures that your application recognizes the latest
SPDX license identifiers.

Usage:
    python manage.py update_spdx_licenses
"""

import os
import requests
from django.conf import settings
from django.core.management.base import BaseCommand

SPDX_URL = "https://spdx.org/licenses/licenses.json"

class Command(BaseCommand):
    """
    Django management command to update the SPDX license list.

    Downloads the latest SPDX licenses.json file and stores it at the path
    specified by the SPDX_LICENSES_PATH setting. This allows your application
    to use the most current SPDX license identifiers for validation and choices.
    """

    help = "Download and update the SPDX license list (licenses.json)"

    def handle(self, *args, **options):
        """
        Entry point for the management command.

        Downloads the SPDX license list from the official SPDX URL and writes it
        to the designated location in the project. Creates the destination
        directory if it does not exist.

        Raises:
            requests.HTTPError: If the download fails.
            OSError: If writing the file fails.
        """
        dest_path = settings.SPDX_LICENSES_PATH
        dest_dir = os.path.dirname(dest_path)
        os.makedirs(dest_dir, exist_ok=True)
        self.stdout.write(f"Downloading SPDX license list from {SPDX_URL}...")
        response = requests.get(SPDX_URL, timeout=10)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            f.write(response.content)
        self.stdout.write(self.style.SUCCESS(f"SPDX license list updated at {dest_path}"))
