"""API views for core_directory"""
import os

from dataclasses import dataclass

import requests

from django.http import HttpResponse
from django.views.generic import TemplateView

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from github import Github
from github import GithubException, UnknownObjectException
from github.Auth import Token as GitHubAuthToken

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import CorePackage
from ..serializers import CoreSerializer

class APIDocsLandingPageView(TemplateView):
    """Landing page for API documentation."""
    template_name = "api_docs/index.html"

def extend_schema_with_429(**kwargs):
    """
    Decorator that merges a 429 response into the responses dict for extend_schema.
    """
    responses = kwargs.pop('responses', {})
    responses = {
        **responses,
        429: OpenApiResponse(description="Rate limit exceeded. Too many requests."),
    }
    return extend_schema(responses=responses, **kwargs)

class HealthCheckView(APIView):
    """API health check endpoint."""
    @extend_schema_with_429(
        summary="Health Check",
        description="Returns the health status of the API.",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {
                        'type': 'string',
                        'example': 'ok',
                        'description': 'Indicates that the API is healthy.'
                    }
                }
            }
        }
    )
    def get(self, request, *args, **kwargs):
        """Return the health status of the API.

        Returns:
            Response: JSON object with status 'ok'.
        """
        # Perform any necessary checks here, such as database connectivity
        return Response({'status': 'ok'}, status=200)

class Cores(APIView):
    """Endpoint for listing all available core packages in the database."""
    @extend_schema_with_429(
        summary='List all cores',
        description=(
            'turns a list of all core packages available in FuseSoC-PD, '
            'optionally filtered by a keyword in the VLNV name.'
        ),
        responses={200: OpenApiResponse(description='List of all available cores')},
        parameters=[
            OpenApiParameter(
                name='filter',
                description='Keyword to filter cores by their names',
                required=False,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY
            )
        ]
    )
    def get(self, request, *args, **kwargs):
        """List all available core packages, optionally filtered by a keyword.

        Returns:
            Response: List of core VLNV names or error message.
        """
        filter_keyword = request.query_params.get('filter', '')

        available_cores = (
            CorePackage.objects
            .filter(vlnv_name__icontains=filter_keyword)
            .order_by('vlnv_name')
            .values_list('vlnv_name', flat=True)
        )
        return Response(available_cores, status=status.HTTP_200_OK)


class GetCore(APIView):
    """Endpoint for downloading a FuseSoC core package file by VLNV name."""
    @extend_schema_with_429(
        summary='Download a FuseSoC Core Package',
        description='Provide the FuseSoC Core Package as a .core file to the user.',
        parameters=[
            OpenApiParameter(
                name='core',
                description='Downloads the `.core` file for a given core package (identified by its VLNV name).',
                required=True,
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY
            )
        ],
        responses={
            200: OpenApiResponse(description='FuseSoC Core Package successfully retrieved'),
            404: OpenApiResponse(description='FuseSoC Core Package not found')
        }
    )
    def get(self, request):
        """Download a FuseSoC core package file by VLNV name.

        Query Parameters:
            core (str): The VLNV name of the core package to download (e.g., 'acme:lib1:foo:1.0.0').

        Returns:
            HttpResponse: The core file as an attachment, or error message if not found.
        """
        requested_core_vlnv = request.query_params.get('core', '')

        if not requested_core_vlnv:
            return Response(
                {'error': 'Missing required "core" query parameter.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            core_object = CorePackage.objects.get(vlnv_name=requested_core_vlnv)

            requested_file = requests.get(core_object.core_url, timeout=10)
            if requested_file.status_code == 200:
                response = HttpResponse(requested_file.content, content_type='application/octet-stream')
                response['Content-Disposition'] = f'attachment; filename={core_object.sanitized_vlnv}.core'
                return response
            return Response(
                {'error': f'FuseSoC Core Package {requested_core_vlnv} not found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except CorePackage.DoesNotExist:
            return Response(
                {'error': f'FuseSoC Core Package {requested_core_vlnv} not available.'},
                status=status.HTTP_404_NOT_FOUND
            )
class Publish(APIView):
    """Endpoint for publishing a new core file to FuseSoC Package Directory."""
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema_with_429(
        summary='Publish a core file',
        description=(
            'Validates and publishes a core file to FuseSoC Package Directory. '
            'The core file should be uploaded as a multipart/form-data request. '
            'On success, the directory is updated with the new core package.'
        ),
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'core_file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'The core file to be published',
                        'contentMediaType': 'application/x-yaml'
                    },
                    'signature_file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Optional signature file for the core file',
                        'contentMediaType': 'application/pgp-signature'
                    }
                },
                'required': ['core_file']
            }
        },
        responses={
            201: OpenApiResponse(description='Core published successfully'),
            400: OpenApiResponse(description='Error message indicating why the validation failed')
        }
    )
    def post(self, request, *args, **kwargs):
        """Validate and publish a core file to FuseSoC Package Directory.

        Returns:
            Response: Success message or error message.
        """
        @dataclass
        class CoreData:
            """
            Container for core file publishing data.

            Attributes:
                vlnv_name (str): The VLNV (Vendor:Library:Name:Version) name of the core.
                sanitized_name (str): A sanitized version of the core name, suitable for filenames.
                core_file (Any): The uploaded core file object.
                signature_file (Any, optional): The uploaded signature file object, if provided.
                core_url (str, optional): The URL of the core file in the GitHub repository.
                sig_url (str, optional): The URL of the signature file in the GitHub repository.
            """
            vlnv_name: str
            sanitized_name: str
            core_file: any
            signature_file: any = None
            core_url: str = None
            sig_url: str = None

            @property
            def core_file_name(self):
                """Returns the filename for the core file."""
                return f'{self.sanitized_name}.core'

            @property
            def signature_file_name(self):
                """Returns the filename for the signature file."""
                return f'{self.sanitized_name}.core.sig'

            def read_core_content(self):
                """Reads and decodes the core file content as UTF-8."""
                self.core_file.seek(0)
                return self.core_file.read().decode('utf-8')

            def read_signature_content(self):
                """Reads and decodes the signature file content as UTF-8, if present."""
                if self.signature_file:
                    self.signature_file.seek(0)
                    return self.signature_file.read().decode('utf-8')
                return None

        serializer = CoreSerializer(data=request.data)

        if serializer.is_valid():

            vlnv_name = serializer.validated_data['vlnv_name']
            # Check if a core with this VLNV already exists in the database
            if CorePackage.objects.filter(vlnv_name=vlnv_name).exists():
                return Response(
                    {'error': f'Core \'{vlnv_name}\' already exists in FuseSoC Package Directory.'},
                    status=status.HTTP_409_CONFLICT
                )

            core_data = CoreData(
                vlnv_name = serializer.validated_data['vlnv_name'],
                core_file = serializer.validated_data['core_file'],
                sanitized_name = serializer.validated_data['sanitized_name'],
                signature_file = serializer.validated_data.get('signature_file')
            )

            # Initialize GitHub client
            g = Github(auth=GitHubAuthToken(os.getenv('GITHUB_ACCESS_TOKEN')))
            repo = g.get_repo(os.getenv('GITHUB_REPO'))

            # Read and encode the core file content
            encoded_core_content = core_data.read_core_content()

            try:
                # Try to get the core from the repository
                _ = repo.get_contents(core_data.core_file_name)
                # The core already exists -> do not create again
                return Response(
                    {'message': f'Core \'{core_data.vlnv_name}\' already exists in FuseSoC Package Directory.'},
                    status=status.HTTP_409_CONFLICT
                )
            except (UnknownObjectException, IndexError, GithubException):
                try:
                    # If the core does not exist, create it
                    result = repo.create_file(
                        core_data.core_file_name,
                        f'Add FuseSoC core {core_data.vlnv_name}',
                        encoded_core_content,
                        branch='main')

                    # Get core url from GitHub and add core to database
                    serializer.validated_data['core_url'] = result['content'].download_url

                    # Handle the optional signature file
                    if encoded_signature_content := core_data.read_signature_content():
                        result = repo.create_file(
                            core_data.signature_file_name,
                            f'Add signature for {core_data.vlnv_name}',
                            encoded_signature_content,
                            branch='main'
                        )

                        serializer.validated_data['sig_url'] = result['content'].download_url

                    # Save new core in DB
                    serializer.save()

                    return Response(
                        {'message': 'Core published successfully'},
                        status=status.HTTP_201_CREATED
                    )
                except GithubException as err:
                    # Handle specific GitHub API errors
                    return Response(
                        {'error': f'GitHub error: {err.data}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class Validate(APIView):
    """Endpoint for validating a core file (before publishing)."""
    @extend_schema_with_429(
        summary='Validate a core file',
        description=(
            'Validates a core file against a predefined JSON schema. '
            'The core file should be uploaded as a multipart/form-data request.'
        ),
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'core_file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'The core file to be validated'
                    },
                    'signature_file': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Optional signature file for the core file'
                    }
                },
                'required': ['core_file']
            }
        },
        responses={
            200: OpenApiResponse(description='Core file is valid'),
            400: OpenApiResponse(description='Error message indicating why the validation failed')
        }
    )
    def post(self, request, *args, **kwargs):
        """Validate a core file before publishing.

        Returns:
            Response: Validation success or error message.
        """
        file_obj = request.data.get('core_file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CoreSerializer(data=request.data)
        if serializer.is_valid():
            return Response({'message': 'Core file is valid'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
