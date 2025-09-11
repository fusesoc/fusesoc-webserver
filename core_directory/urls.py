"""
URL configuration for the API application.

This module maps URL paths to views for API endpoints and documentation.

API Endpoints:
- '': ExampleView for basic example endpoint.
- 'list/': Cores view for listing core items.
- '<str:package_name>/get/': GetCore view for retrieving specific core items.
- 'validate/': Validate view for handling validation requests.
- 'publish/': Publish view for handling publishing requests.

Documentation:
- 'docs/': APIDocsLandingPageView for the documentation landing page.
- 'docs/schema/': SpectacularAPIView for the OpenAPI schema.
- 'docs/swagger/': SpectacularSwaggerView for Swagger UI.
- 'docs/redoc/': SpectacularRedocView for ReDoc UI.

Dependencies:
- drf_spectacular for API documentation.
- Django for URL routing and view handling.
"""

from django.urls import path, include
from django.views.generic import RedirectView

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .views.api_views import APIDocsLandingPageView, HealthCheckView, Validate, Publish, Cores, GetCore

app_name = "core_directory"

urlpatterns = [
   # API URLs
    path('v1/', include([
        # API Endpoints
        path('', RedirectView.as_view(url='docs/', permanent=True), name='redirect_to_docs'),
        path('health/', HealthCheckView.as_view(), name='health_check'),
        path('list/', Cores.as_view(), name='core_list'),
        path('<str:package_name>/get/', GetCore.as_view(), name='core_get'),
        path('validate/', Validate.as_view(), name='validate'),
        path('publish/', Publish.as_view(), name='publish'),

        # Documentation
        path('docs/', APIDocsLandingPageView.as_view(), name='api_docs_landing'),
        path('docs/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('docs/swagger/', SpectacularSwaggerView.as_view(url_name='core_directory:schema'), name='swagger_ui'),
        path('docs/redoc/', SpectacularRedocView.as_view(url_name='core_directory:schema'), name='redoc_ui'),
    ])),
]
