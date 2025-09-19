"""Web views for core_directory"""

from django.db.models import Count, Prefetch
from django.db.models.functions import Lower
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from ..models import CorePackage, Project, Vendor, Library

def landing(request):
    """Render the landing page with core and vendor counts."""
    return render(request, 'web_ui/landing.html',
                  {
                      'num_cores': Project.objects.count(),
                      'num_vendors': Vendor.objects.count(),
                  }
                )

def core_package_list(request):
    """Render a list of core packages, optionally filtered by search query."""
    search_query = request.GET.get('search', '')
    if search_query:
        core_packages = CorePackage.objects.filter(vlnv_name__icontains=search_query)
    else:
        core_packages = CorePackage.objects.all()

    core_packages = core_packages.annotate(
        vlnv_lower=Lower('vlnv_name')
    ).order_by('vlnv_lower')
    return render(request, 'web_ui/core_packages_list.html', {'core_packages': core_packages})

def core_detail(request, pk=None):
    """Render the detail page for a core package, including its targets and dependencies."""
    if pk is not None:
        core = get_object_or_404(CorePackage, pk=pk)
    else:
        raise Http404("CorePackage not found.")

    # Prefetch filesets and their dependencies for each target
    target_configurations = core.target_configurations.prefetch_related('filesets__dependencies')

    # Prepare a list of dicts: each with the target and its dependencies (flat list)
    targets_with_deps = []
    for target_configuration in target_configurations:
        # Collect all dependency core names from all filesets in this target
        dependencies = set()
        filetypes = set()
        for fileset in target_configuration.filesets.all():
            if fileset.file_type:
                filetypes.add(fileset.file_type)
            for dep in fileset.dependencies.all():
                dependencies.add(dep.dependency_core_name)
        targets_with_deps.append({
            'target_configuration': target_configuration,
            'dependencies': sorted(dependencies),
            'filetypes': sorted(filetypes)
        })

    context = {
        'core': core,
        'targets_with_deps': targets_with_deps,
    }
    return render(request, 'web_ui/core_detail.html', context)

def core_detail_by_vlnv(request, vendor, library, core, version):
    """Render the core detail page by looking up objects using vendor, library, core, and version."""
    # Look up the related objects
    vendor_obj = get_object_or_404(Vendor, sanitized_name=vendor)
    if library == '~':
        # This represents no library (blank sanitized_name)
        library_obj = get_object_or_404(Library, vendor=vendor_obj, sanitized_name='')
    else:
        library_obj = get_object_or_404(Library, vendor=vendor_obj, sanitized_name=library)
    project_obj = get_object_or_404(Project, vendor=vendor_obj, library=library_obj, sanitized_name=core)
    core_package = get_object_or_404(CorePackage, project=project_obj, version=version)
    return core_detail(request, core_package.pk)

def vendor_list(request):
    """Render a list of core vendors, optionally filtered by search query."""
    search_query = request.GET.get('search', '')
    if search_query:
        vendors = Vendor.objects.filter(name__icontains=search_query)
    else:
        vendors = Vendor.objects.all()

    vendors = vendors.annotate(
        num_cores=Count('project', distinct=True),
        num_libraries=Count('libraries', distinct=True)
    ).order_by('sanitized_name')
    return render(request, 'web_ui/vendor_list.html', {'vendors': vendors})

def vendor_detail(request, sanitized_name=None):
    """Render the detail page for a core package, including its targets and dependencies."""
    vendor = get_object_or_404(Vendor, sanitized_name=sanitized_name)

    # Prefetch projects for each library, and for each project prefetch versions (core packages)
    # Projects and libraries are ordered by sanitized_name
    # CorePackage (versions) are ordered by Meta.ordering (semantic version order)
    project_qs = Project.objects.order_by('sanitized_name').prefetch_related('versions')
    libraries = vendor.libraries.order_by('sanitized_name').prefetch_related(
        Prefetch('projects', queryset=project_qs)
    )

    context = {
        'vendor': vendor,
        'libraries': libraries,
    }
    return render(request, 'web_ui/vendor_detail.html', context)
