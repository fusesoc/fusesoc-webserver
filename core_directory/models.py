"""
Models for FuseSoC package database: vendors, libraries, projects, versions, filesets, dependencies, and targets.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from semver import VersionInfo
from utils.sanitize import get_unique_sanitized_name
from utils.spdx import get_spdx_choices, get_spdx_license_url, validate_spdx

class UniqueSanitizedNameMixin(models.Model):
    """Mixin for unique sanitized_name field."""
    sanitized_name = models.CharField(max_length=255, unique=True)

    class Meta:
        """Abstract base for sanitized name mixin."""
        abstract = True

    def get_sanitized_source(self):
        """Source string for sanitization (default: name)."""
        return getattr(self, 'name', None)

    def save(self, *args, **kwargs):
        if not self.sanitized_name:
            self.sanitized_name = get_unique_sanitized_name(
                self.__class__,
                self.get_sanitized_source(),
                field='sanitized_name',
                instance=self
            )
        super().save(*args, **kwargs)

class Vendor(UniqueSanitizedNameMixin):
    """Represents a vendor."""
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        """Return the vendors's name as its string representation."""
        return f'{self.name}'

    def get_absolute_url(self):
        """
        Returns the canonical URL for this vendor.
        """
        return reverse('vendor-detail', kwargs={'sanitized_name': self.sanitized_name})


class Library(UniqueSanitizedNameMixin):
    """Represents a library for a vendor."""
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='libraries')
    name = models.CharField(max_length=255, blank=True)

    class Meta:
        """Ensure library name is unique per vendor."""
        unique_together = ('vendor', 'name')

    def __str__(self):
        """Return the library's name as its string representation."""
        return f'{self.vendor}:{self.name}'

class Project(UniqueSanitizedNameMixin):
    """
    Represents a FuseSoC core project.

    Each project can have multiple versions.
    """
    name = models.CharField(
        max_length=255,
        help_text='The name of the project as specified in the .core file.'
    )
    description = models.CharField(
        max_length=255,
        help_text='A short description of the core package.'
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    library = models.ForeignKey(Library, on_delete=models.CASCADE, related_name='projects')

    class Meta:
        """Ensure project name is unique per vendor and library."""
        unique_together = ('vendor', 'library', 'name')

    def __str__(self):
        """Return the core's name as its string representation."""
        return f'{self.vendor.name}:{self.library.name}:{self.name}'

class CorePackage(UniqueSanitizedNameMixin):
    """Represents a specific version of a core project."""
    project = models.ForeignKey(
        Project,
        related_name='versions',
        on_delete=models.CASCADE
    )
    vlnv_name  = models.CharField(
        max_length=255,
        help_text='The name of the core with version as specified in the .core file.'
    )
    version = models.CharField(
        max_length=50,
        help_text="Full version string, e.g. '1.2.3-abc'."
    )
    version_major = models.IntegerField(
        help_text="Major version number (e.g. 1 for version '1.2.3-abc')."
    )
    version_minor = models.IntegerField(
        help_text="Minor version number (e.g. 2 for version '1.2.3-abc')."
    )
    version_patch = models.IntegerField(
        help_text="Patch version number (e.g. 3 for version '1.2.3-abc')."
    )
    version_prerelease = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Pre-release label (e.g. 'abc' for version '1.2.3-abc')."
    )
    core_url = models.URLField(
        help_text='URL to download the .core file from GitHub or another source.'
    )
    sig_url = models.URLField(
        blank=True,
        null=True,
        help_text='Optional URL to download the .sig file for signature verification.'
    )
    description = models.CharField(
        max_length=255,
        help_text='A short description of the core package.'
    )
    spdx_license = models.CharField(
        max_length=64,
        choices=get_spdx_choices,
        validators=[validate_spdx],
        blank=True,
        null=True,
        help_text="SPDX license identifier (e.g., MIT, GPL-3.0-or-later, or LicenseRef-...)"
    )


    @property
    def is_signed(self):
        """
        Returns True if sig_url is set and valid, False otherwise.
        You can add more validation logic if needed.
        """
        return bool(self.sig_url)

    @property
    def sanitized_vlnv(self):
        """
        Returns a filesystem- and URL-safe version of the core's VLNV (Vendor:Library:Name:Version),
        with colons and other problematic characters replaced by underscores.
        """
        return (
            f'{self.project.vendor.sanitized_name}_'
            f'{self.project.library.sanitized_name}_'
            f'{self.project.sanitized_name}_'
            f'{self.sanitized_name}'
        )

    class Meta:
        """Ensure version is unique per project."""
        unique_together = ('project', 'version')

        ordering = [
            'project__vendor__name',
            'project__name',
            'version_major',
            'version_minor',
            'version_patch',
            'version_prerelease'
        ]

    def __str__(self):
        """Return project and version."""
        return f"{self.project}:{self.version}"

    def get_sanitized_source(self):
        """Provides version for sanitized name mixin."""
        return getattr(self, 'version', None)

    def get_license_url(self):
        """
        Returns the SPDX license URL for this core, or None if not available.
        """
        if self.spdx_license:
            return get_spdx_license_url(self.spdx_license)
        return None

    def get_absolute_url(self):
        """
        Returns the canonical URL for this core package version.
        """
        return reverse('core-detail-vlnv', kwargs={
            'vendor': self.project.vendor.sanitized_name,
            'library': self.project.library.sanitized_name or '~',
            'core': self.project.sanitized_name,
            'version': self.sanitized_name,
        })

    def clean(self):
        """
        Validates that the version string is a valid semantic version with all components.
        """
        try:
            _ = VersionInfo.parse(self.version)
        except ValueError as e:
            raise ValidationError({'version': "Invalid version string."}) from e

    def save(self, *args, **kwargs):
        """
        Parses the version string and updates version fields before saving.

        Extracts major, minor, patch, and pre-release components from `version`
        and stores them in the corresponding fields.
        """
        # Validate user-supplied fields, ignore derived fields for now
        self.full_clean(
            exclude = [
                'sanitized_name',
                'version_major',
                'version_minor',
                'version_patch',
                'version_prerelease'
                ]
            )

        semver = VersionInfo.parse(self.version)

        self.version_major = semver.major
        self.version_minor = semver.minor
        self.version_patch = semver.patch
        self.version_prerelease = semver.prerelease or ''

        # Validate everything now that all fields are set
        # (except sanitized_name which is set in super().save(...))
        self.full_clean(exclude=['sanitized_name'])
        super().save(*args, **kwargs)

class Fileset(models.Model):
    """Represents a fileset within a core package."""
    core_package = models.ForeignKey(
        CorePackage,
        related_name='filesets',
        on_delete=models.CASCADE,
        help_text='The core package this fileset belongs to.'
    )
    name = models.CharField(
        max_length=100,
        help_text='The name of the fileset as specified in the .core file.'
    )
    files = models.JSONField(
        null=True,
        blank=True,
        help_text='List of files in this fileset.'
    )
    file_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text='Type of files in this fileset (e.g., verilogSource).'
    )

    def __str__(self):
        """Return a string identifying the fileset and its core."""
        return f'{self.core_package}:{self.name}'

class FilesetDependency(models.Model):
    """Represents a dependency of a fileset on another core."""
    fileset = models.ForeignKey(
        Fileset,
        related_name='dependencies',
        on_delete=models.CASCADE,
        help_text='The fileset that has this dependency.'
    )
    dependency_core_name = models.CharField(
        max_length=255,
        help_text='The name of the core package this fileset depends on.'
    )
    dependency_condition = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='Optional target parameter to indicate the dependency.'
    )
    core_package = models.ForeignKey(
        CorePackage,
        related_name='dependencies',
        on_delete=models.CASCADE,
        help_text='The core package that has this dependency.'
    )

    def __str__(self):
        """Return a string describing the dependency relationship."""
        return f'{self.fileset} depends on {self.dependency_core_name}'

class Target(models.Model):
    """Represents a build or simulation target for a core package."""
    name = models.CharField(
        max_length=100,
        help_text='The name of the target as specified in the .core file.'
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text='Description of this target.'
    )

    def __str__(self):
        """Return a string identifying the target."""
        return f'{self.name}'

class TargetConfiguration(models.Model):
    """Represents a build or simulation target configuration for a core package."""
    core_package = models.ForeignKey(
        CorePackage,
        related_name='target_configurations',
        on_delete=models.CASCADE,
        help_text='The core package this target belongs to.'
    )
    target = models.ForeignKey(
        Target,
        related_name='target_configurations',
        on_delete=models.CASCADE,
        help_text='The core package this target belongs to.'
    )
    filesets = models.ManyToManyField(
        Fileset,
        related_name='target_configurations',
        help_text='The filesets included in this target.'
    )
    parameters = models.JSONField(
        null=True,
        blank=True,
        help_text='Optional parameters for this target.'
    )
    default_tool = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='Default tool for this target.'
    )
    flow = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='Flow for this target.'
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text='Description of this target.'
    )

    def __str__(self):
        """Return a string identifying the target and its core."""
        return f'{self.core_package}:{self.target.name}'
