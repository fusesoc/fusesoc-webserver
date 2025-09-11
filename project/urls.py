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
from django.contrib import admin
from django.urls import include, path

from core_directory.views.web_views import (
    landing,
    core_detail,
    core_package_list,
    core_detail_by_vlnv,
    vendor_list,
    vendor_detail
)

urlpatterns = [

    path('', landing, name='landing'),
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

    path('admin/', admin.site.urls),
    path('api/', include('core_directory.urls')),
]
