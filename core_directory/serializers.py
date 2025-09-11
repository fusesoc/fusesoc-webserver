"""
Module: core_serializer

This module provides the `CoreSerializer` class for validating core and signature files. It ensures that
files have the correct extensions, are within size limits, and conform to specified JSON schemas. The
serializer also extracts and verifies the core name from the core file and checks its consistency with
the signature file. Additionally, it validates that the core file starts with the required "CAPI=2:" header
and passes FuseSoC's Core2Parser validation.

Classes:
    CoreSerializer: Validates core and signature files, checking extensions, sizes, and YAML content
                    against JSON schemas. It also extracts and verifies the core name, and performs
                    FuseSoC core file validation.

Dependencies:
    - os: For file path operations.
    - json: For loading JSON schema files.
    - yaml: For parsing YAML content.
    - jsonschema: For validating YAML content against JSON schemas.
    - fusesoc.capi2.coreparser.Core2Parser: For FuseSoC core file validation.

Usage:
    Use `CoreSerializer` to validate file uploads, ensuring they meet specified criteria and raising
    validation errors if any checks fail.
"""

import os
import re
import json
import yaml

from django.db import transaction
from rest_framework import serializers
from jsonschema import validate, ValidationError, SchemaError
from fusesoc.capi2.coreparser import Core2Parser

from utils.sanitize import sanitize_string
from utils.spdx import validate_spdx
from utils.vlnv import VLNV
from .models import Project, Vendor, Library, CorePackage, Fileset, FilesetDependency, Target, TargetConfiguration

class CoreSerializer(serializers.Serializer):
    """
    Serializer for validating core and signature files.

    This serializer checks file extensions, file sizes, and validates YAML content
    against JSON schemas. It also extracts the core name from the core file and
    ensures consistency with the signature file if provided.

    Fields:
        core_file (FileField): Required. Must have a `.core` extension.
        signature_file (FileField): Optional. Must have a `.sig` extension if provided.
        core_name (CharField): Read-only. Extracted from the core file.

    Methods:
        validate_core_file(value): Validates the core file's extension and size.
        validate_signature_file(value): Validates the signature file's extension and size.
        validate(attrs): Performs comprehensive validation, including schema checks and
                         core name consistency.
    """

    # User-uploaded files
    core_file = serializers.FileField()
    signature_file = serializers.FileField(required=False)

    # Optionally, allow user to provide URLs
    core_url = serializers.URLField(required=False)
    sig_url = serializers.URLField(required=False, allow_null=True)

    # Read-only fields extracted from the core file
    vlnv_name = serializers.CharField(read_only=True, max_length=255)
    sanitized_name = serializers.CharField(read_only=True, max_length=255)
    vendor_name = serializers.CharField(read_only=True, max_length=255)
    library_name = serializers.CharField(read_only=True, max_length=255)
    project_name = serializers.CharField(read_only=True, max_length=255)
    version = serializers.CharField(read_only=True, max_length=255)
    description = serializers.CharField(read_only=True, max_length=255, required=False)
    spdx_license = serializers.CharField(read_only=True, max_length=64)

    def validate_core_file(self, value):
        """
        Validates the core file's extension and size.

        Ensures the file has a `.core` extension and does not exceed 64KB.
        Raises a ValidationError if these conditions are not met.
        """
        if not value.name.endswith('.core'):
            raise serializers.ValidationError("Only .core files are allowed.")
        if value.size > 64 * 1024:
            raise serializers.ValidationError('Core file is too large')
        return value

    def validate_signature_file(self, value):
        """
        Validates the signature file's extension and size.

        Ensures the file has a `.sig` extension and does not exceed 10KB.
        Raises a ValidationError if these conditions are not met.
        """
        if not value.name.endswith('.sig'):
            raise serializers.ValidationError("Only .sig files are allowed for signature.")
        if value.size > 10 * 1024:
            raise serializers.ValidationError('Signature file is too large')
        return value

    def validate(self, attrs):
        """
        Performs comprehensive validation of the uploaded core and optional signature files.

        This method checks:
            - The core file starts with the required "CAPI=2:" header.
            - Both files are valid YAML and conform to their respective JSON schemas.
            - The core file passes FuseSoC's Core2Parser validation.
            - The `name` property exists in the core file.
            - If the license if valid (if available)
            - If a signature file is provided, its core name matches the core file.

        Raises:
            serializers.ValidationError: If any validation step fails.
        """
        current_dir = os.path.dirname(__file__)

        try:
            # Check if first line is 'CAPI=2'
            first_line = attrs['core_file'].readline().decode('utf-8').strip()
            if not first_line.startswith('CAPI=2:'):
                raise serializers.ValidationError(
                    'Core file does not start with "CAPI=2:", see '
                    'https://fusesoc.readthedocs.io/en/stable/user/build_system/core_files.html#the-first-line-capi-2'
                )
            attrs['core_file'].seek(0)

            core_content_yaml = yaml.safe_load(attrs['core_file'])
            self._validate_against_schema(
                core_content_yaml,
                os.path.join(current_dir, 'core_schema.json'),
                'core'
            )

            del core_content_yaml['CAPI=2']
            Core2Parser().validate(core_content_yaml)

            core_vlnv = VLNV.from_string(core_content_yaml.get('name'))

            attrs.update({
                'vlnv_name': core_vlnv.to_string(),
                'vendor_name': core_vlnv.vendor,
                'library_name': core_vlnv.library,
                'project_name': core_vlnv.name,
                'version': core_vlnv.version,
                'description': core_content_yaml.get('description'),
                'core_content_yaml': core_content_yaml,
            })

            spdx_license_id = core_content_yaml.get('license')

            if spdx_license_id:
                try:
                    validate_spdx(spdx_license_id)
                except Exception as e:
                    raise serializers.ValidationError({'spdx_license': str(e)})


            attrs['spdx_license'] = spdx_license_id

            if attrs.get('signature_file'):
                sig_content_yaml = yaml.safe_load(attrs['signature_file'])
                sig_schema_path = os.path.join(current_dir, 'sig_schema.json')
                self._validate_against_schema(sig_content_yaml, sig_schema_path, 'signature')

                signature_vlnv =  VLNV.from_string(sig_content_yaml.get('coresig').get('name'))

                if core_vlnv != signature_vlnv:
                    raise serializers.ValidationError(
                        f'Signature error: Signature file not valid for {core_vlnv}. '
                        f'Signature file was created for {signature_vlnv}.'
                    )
                attrs['signature_file'].seek(0)

            with transaction.atomic():
                vendor  = Vendor.objects.filter(name=core_vlnv.vendor).first()
                library = Library.objects.filter(vendor=vendor, name=core_vlnv.library).first()
                project = Project.objects.filter(vendor=vendor, library=library, name=core_vlnv.name).first()

                sanitized_vendor  = vendor.sanitized_name  if vendor  else sanitize_string(core_vlnv.vendor)
                sanitized_library = library.sanitized_name if library else sanitize_string(core_vlnv.library)
                sanitized_project = project.sanitized_name if project else sanitize_string(core_vlnv.name)
                sanitized_version = sanitize_string(core_vlnv.version)

                attrs['sanitized_name'] = (
                    f'{sanitized_vendor}_{sanitized_library}_{sanitized_project}_{sanitized_version}'
                )

        except SyntaxError as e:
            # Might be thrown by FuseSoC Core2Parser if validation fails.
            raise serializers.ValidationError(
                f"Core file did not pass FuseSoC core validation: {e.msg}"
            )
        except yaml.MarkedYAMLError as e:
            raise serializers.ValidationError(
                f"Error in file {e.problem_mark.name} "
                f"(line {e.problem_mark.line}, column {e.problem_mark.column}): "
                f"{e.problem}"
            )
        except yaml.YAMLError as e:
            raise serializers.ValidationError(f'Error while parsing file: {str(e)}')

        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            # Get or create Vendor, Library, Project
            vendor, _ = Vendor.objects.get_or_create(name=validated_data['vendor_name'])
            library, _ = Library.objects.get_or_create(vendor=vendor, name=validated_data['library_name'])
            project, _ = Project.objects.get_or_create(
                vendor=vendor,
                library=library,
                name=validated_data['project_name']
            )

            # Create an save the model instance
            instance = CorePackage.objects.create(
                project=project,
                vlnv_name=validated_data['vlnv_name'],
                version=validated_data['version'],
                core_url=validated_data.get('core_url'),
                sig_url=validated_data.get('sig_url'),
                description=validated_data.get('description'),
                spdx_license=validated_data.get('spdx_license')
            )

            # Create Filesets and their Dependencies
            fileset_objs = {}
            for fs_name, fs_data in validated_data['core_content_yaml'].get('filesets', {}).items():
                fileset = Fileset.objects.create(
                    core_package=instance,
                    name=fs_name,
                    files=fs_data.get('files'),
                    file_type=fs_data.get('file_type'),
                )

                fileset_objs[fs_name] = fileset

                for dep in fs_data.get('depend', []):
                    match = re.match(r'^(.*?)\?\s*\((.*?)\)$', dep)
                    if match:
                        dependency_condition = match.group(1).strip()
                        dependency_core_name = match.group(2).strip()
                    else:
                        dependency_core_name = dep.strip()
                        dependency_condition = None

                    FilesetDependency.objects.create(
                        fileset=fileset,
                        dependency_core_name=dependency_core_name,
                        dependency_condition=dependency_condition,
                        core_package=instance
                    )

            # Create Targets and link Filesets
            targets = validated_data['core_content_yaml'].get('targets', {})
            for tgt_name, tgt_data in targets.items():
                target, _ = Target.objects.get_or_create(name=tgt_name)
                target_config = TargetConfiguration.objects.create(
                    core_package=instance,
                    target=target,
                    parameters=tgt_data.get('parameters'),
                    default_tool=tgt_data.get('default_tool'),
                    flow=tgt_data.get('flow'),
                    description=tgt_data.get('description')
                )
                for fs_name in tgt_data.get('filesets', []):
                    fs_obj = fileset_objs.get(fs_name)
                    if fs_obj:
                        target_config.filesets.add(fs_obj)

            return instance

    def update(self, instance, validated_data):
        """
        Required by BaseSerializer. No-op implementation.
        """

    def _validate_against_schema(self, yaml_content, schema_path, file_type):
        """
        Validates YAML content against a specified JSON schema.

        Raises a ValidationError if the content does not conform to the schema.
        """
        with open(schema_path, 'r', encoding='utf-8') as schema_file:
            try:
                json_schema = json.load(schema_file)
                validate(instance=yaml_content, schema=json_schema)
            except ValidationError as e:
                raise serializers.ValidationError(self._format_core_validation_error(e, file_type))
            except SchemaError as e:
                raise serializers.ValidationError(
                    f'Internal error: invalid schema to validate {file_type} ({e.message})'
                )
            except json.decoder.JSONDecodeError as e:
                raise serializers.ValidationError(
                    f'Internal error: invalid schema to validate {file_type} ({str(e)})'
                )

    def _format_core_validation_error(self, e, file_type):
        """
        Formats validation error messages for schema validation errors.

        Provides detailed error information for easier debugging.
        """
        validator_error_messages = {
            'CAPI=2': {},
            'name': {
                'pattern': (
                    'Core name does not match requirements. See '
                    'https://fusesoc.readthedocs.io/en/stable/user/build_system/'
                    'core_files.html#the-core-name-version-and-description'
                ),
            },
            'license': {
                'type': (
                    'Custom license objects are not supported. '
                    'Please use an SPDX identifier string.'
                )
            }
        }
        key = '::'.join(e.path)
        default_message = {'default': e.message}
        error_message =  validator_error_messages.get(key, default_message).get(e.validator, e.message)
        return f'Validation error in {file_type}::{key}: {error_message}'
