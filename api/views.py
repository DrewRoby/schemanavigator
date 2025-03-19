# views.py
import os
import random
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

@api_view(['GET'])
def get_images(request):
    """
    API endpoint that returns a list of all images in the rsps directory.
    """
    # Path to the rsps directory, relative to your MEDIA_ROOT
    rsps_dir = os.path.join(settings.MEDIA_ROOT, 'images', 'rsps')
    
    # Check if directory exists
    if not os.path.exists(rsps_dir):
        return Response(
            {"error": "Image directory not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all files in the directory
    try:
        files = os.listdir(rsps_dir)
        
        # Filter out non-image files by extension
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        image_files = [
            file for file in files 
            if os.path.splitext(file)[1].lower() in image_extensions
        ]
        
        return Response({
            "status": "success",
            "count": len(image_files),
            "images": image_files
        })
    
    except Exception as e:
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def get_random_image(request):
    """
    API endpoint that returns a random image from the rsps directory.
    """
    # Path to the rsps directory, relative to your MEDIA_ROOT
    rsps_dir = os.path.join(settings.MEDIA_ROOT, 'images', 'rsps')
    
    # Check if directory exists
    if not os.path.exists(rsps_dir):
        return Response(
            {"error": "Image directory not found"}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all files in the directory
    try:
        files = os.listdir(rsps_dir)
        
        # Filter out non-image files by extension
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        image_files = [
            file for file in files 
            if os.path.splitext(file)[1].lower() in image_extensions
        ]
        
        if not image_files:
            return Response(
                {"error": "No images found in directory"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Select a random image
        random_image = random.choice(image_files)
        
        # Construct the URL (adjust as needed for your MEDIA_URL configuration)
        image_url = f"{settings.MEDIA_URL}images/rsps/{random_image}"
        
        return Response({
            "status": "success",
            "image": random_image,
            "url": image_url
        })
    
    except Exception as e:
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
