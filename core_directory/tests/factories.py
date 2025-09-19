import factory
from core_directory.models import Vendor, Library, Project, CorePackage

class VendorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Vendor

    name = factory.Sequence(lambda n: f"vendor{n}")

class LibraryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Library

    vendor = factory.SubFactory(VendorFactory)
    name = factory.Sequence(lambda n: f"library{n}")

class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    vendor = factory.SubFactory(VendorFactory)
    library = factory.SubFactory(LibraryFactory, vendor=factory.SelfAttribute('..vendor'))
    name = factory.Sequence(lambda n: f"project{n}")
    description = "A test project"

class CorePackageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CorePackage

    project = factory.SubFactory(ProjectFactory)
    vlnv_name = factory.Sequence(lambda n: f"vendor:library:project:{n}.0.0")
    version = factory.Sequence(lambda n: f"{n}.0.0")
    core_url = "https://example.com/core.core"
    description = "A test core package"