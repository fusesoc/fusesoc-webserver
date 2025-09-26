"""System views for core_directory"""

from django.http import HttpResponse
from django.conf import settings

def robots_txt(request):
    """
    Serve the robots.txt file based on the site's indexability setting.
    """
    if settings.INDEXABLE:
        content = "User-agent: *\nDisallow:"
    else:
        content = "User-agent: *\nDisallow: /"
    return HttpResponse(content, content_type="text/plain")
