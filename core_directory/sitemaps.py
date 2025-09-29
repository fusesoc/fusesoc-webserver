"""
This module defines sitemap classes for the Django application.
Classes:
    ProjectSitemap: Generates sitemap entries for all Project objects.
    CorePackageSitemap: Generates sitemap entries for all CorePackage objects.
    StaticViewSitemap: Generates sitemap entries for static views such as 'landing',
    'core-package-list', and 'vendor-list'.
Each sitemap class specifies the change frequency and priority for its entries,
and provides methods to retrieve the items to be included in the sitemap.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import CorePackage, Vendor

class VendorSitemap(Sitemap):
    """
    Sitemap class for listing all Vendor objects.
    Attributes:
        changefreq (str): The frequency at which the vendor pages are likely to change.
        priority (float): The priority of vendor pages in the sitemap.
    Methods:
        items(): Returns a queryset of all Vendor objects to be included in the sitemap.
    """
    changefreq = "daily"
    priority = 0.6

    def items(self):
        return Vendor.objects.all().order_by('sanitized_name', 'pk')

class CorePackageSitemap(Sitemap):
    """
    Sitemap class for CorePackage objects.

    This class defines the sitemap configuration for CorePackage entries,
    specifying how frequently the sitemap should be updated and the priority
    of these entries for search engines.

    Attributes:
        changefreq (str): Suggested frequency of changes for CorePackage objects ("daily").
        priority (float): Priority of CorePackage objects in the sitemap (0.8).

    Methods:
        items(): Returns a queryset of all CorePackage objects to be included in the sitemap.
    """
    changefreq = "daily"
    priority = 0.8
    def items(self):
        return CorePackage.objects.all().order_by('vlnv_name')

class StaticViewSitemap(Sitemap):
    """
    Sitemap for static views in the application.

    Attributes:
        priority (float): The priority of the sitemap entries.
        changefreq (str): How frequently the pages are likely to change.

    Methods:
        items(): Returns a list of static view names to include in the sitemap.
        location(item): Returns the URL for a given static view name.
    """
    priority = 0.5
    changefreq = "weekly"
    def items(self):
        return ['landing', 'core-package-list', 'vendor-list']
    def location(self, item):
        return reverse(item)
