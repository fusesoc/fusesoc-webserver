"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/

Examples::

    Function views
        1. Add an import:  from my_app import views
        2. Add a URL to urlpatterns:  path('', views.home, name='home')

    Class-based views
        1. Add an import:  from other_app.views import Home
        2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')

    Including another URLconf
        1. Import the include() function: from django.urls import include, path
        2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.http import HttpResponseNotFound
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from core_directory.sitemaps import CorePackageSitemap, StaticViewSitemap, VendorSitemap
from core_directory.views.system_views import robots_txt
from core_directory.views.api_views import GetArchive
from core_directory.views.web_views import (
    landing,
    core_detail,
    core_detail_by_vlnv,
    core_package_list,
    core_publish,
    vendor_list,
    vendor_detail
)

sitemaps = {
    'corepackages': CorePackageSitemap,
    'static': StaticViewSitemap,
    'vendors': VendorSitemap,
}

def guarded_sitemap_view(request, *args, **kwargs):
    """
    Return the sitemap if INDEXABLE is True, else return 404.
    """
    if not settings.INDEXABLE:
        return HttpResponseNotFound("Sitemap is disabled.")
    return sitemap(request, *args, **kwargs)

urlpatterns = [

    path('', landing, name='landing'),
    path('publish', core_publish, name='core-publish'),
    path('core/<int:pk>/', core_detail, name='core-detail'),

    path('cores/', core_package_list, name='core-package-list'),
    path(
        'cores/<vendor>/<library>/<core>/<version>/',
        core_detail_by_vlnv,
        name='core-detail-vlnv'
    ),

    path('vendors/', vendor_list, name='vendor-list'),
    path(
        'vendors/<sanitized_name>/',
        vendor_detail,
        name='vendor-detail'
    ),

    path('fusesoc_pd/', GetArchive.as_view(), name='archive_get'),
    path('admin/', admin.site.urls),
    path('api/', include('core_directory.urls')),

    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', guarded_sitemap_view, {'sitemaps': sitemaps}, name='sitemap'),
]
