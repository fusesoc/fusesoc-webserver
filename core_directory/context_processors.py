from django.conf import settings

def seo_settings(request):
    return {'INDEXABLE': settings.INDEXABLE}
