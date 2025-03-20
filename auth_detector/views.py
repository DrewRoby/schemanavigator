from django.http import HttpResponse, HttpResponseForbidden
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
import os

@never_cache
@csrf_exempt
def auth_check_image(request):
    """
    View that returns a 1x1 transparent pixel image if the user is authenticated,
    or a 403 Forbidden response if not authenticated.
    """
    if request.user.is_authenticated:
        # Set CORS headers to allow access from your GitHub Pages domain
        response = HttpResponse(content_type="image/png")
        response["Access-Control-Allow-Origin"] = "https://yourname.github.io"  # Replace with your GitHub Pages domain
        response["Access-Control-Allow-Credentials"] = "true"

        # Get the path to the 1x1 transparent pixel image
        # You'll need to create this image in your static files
        img_path = os.path.join(settings.STATIC_ROOT, 'images', 'auth-check.png')

        # If the image doesn't exist or can't be opened, return a simple response
        try:
            with open(img_path, 'rb') as f:
                response.content = f.read()
        except FileNotFoundError:
            # Generate a 1x1 transparent PNG on the fly
            # This is a base64-encoded 1x1 transparent PNG
            from base64 import b64decode
            transparent_pixel = b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
            )
            response.content = transparent_pixel

        return response
    else:
        return HttpResponseForbidden("Authentication required")