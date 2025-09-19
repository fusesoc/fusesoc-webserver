"""Admin configuration for core_directory."""
from django.contrib import admin

from .models import TargetConfiguration, Vendor, Library, Project, CorePackage, Fileset, FilesetDependency, Target

# Register your models here.
admin.site.register(Vendor)
admin.site.register(Library)
admin.site.register(Project)
admin.site.register(Fileset)
admin.site.register(FilesetDependency)
admin.site.register(Target)
admin.site.register(TargetConfiguration)

@admin.register(CorePackage)
class CorePackageAdmin(admin.ModelAdmin):
    """Admin interface configuration for CorePackage model."""
    readonly_fields = (
        'version_major',
        'version_minor',
        'version_patch',
        'version_prerelease'
    )
