"""
Context processor for SEO-related settings.

Provides the INDEXABLE setting to Django templates for use in meta tags and robots.txt.
"""

from django.conf import settings

def seo_settings(request):
    """
    Add the INDEXABLE setting to the template context.

    Args:
        request: The current HttpRequest object.

    Returns:
        dict: A dictionary with the INDEXABLE setting.
    """
    return {'INDEXABLE': settings.INDEXABLE}
