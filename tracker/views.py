import os
import pandas as pd
import numpy as np
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import DataSource, SchemaDefinition, PrimaryKeyCandidate, SchemaChange, SchemaRelationship
from .forms import DataSourceUploadForm
from fuzzywuzzy import fuzz
from django.core.serializers.json import DjangoJSONEncoder


def home(request):
    recent_sources = DataSource.objects.all().order_by('-upload_date')[:5]
    return render(request, 'tracker/home.html', {
        'title': 'Schema Navigator',
        'recent_sources': recent_sources
    })

def upload(request):
    if request.method == 'POST':
        form = DataSourceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Save the uploaded file
            datasource = form.save(commit=False)
            datasource.original_filename = request.FILES['file'].name
            datasource.save()

            # Process the file to detect schema
            process_file(datasource)

            messages.success(request, f'File "{datasource.original_filename}" successfully uploaded and schema detected!')
            return redirect('datasource_detail', pk=datasource.pk)
    else:
        form = DataSourceUploadForm()

    return render(request, 'tracker/upload.html', {
        'form': form,
        'title': 'Upload Data Source'
    })

def process_file(datasource):
    """
    Process the uploaded file, detect schema, and identify primary keys
    """
    file_path = datasource.file.path
    _, file_extension = os.path.splitext(file_path)

    # Read the file based on its type
    try:
        if file_extension.lower() in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        elif file_extension.lower() == '.csv':
            df = pd.read_csv(file_path)
        else:
            # Unsupported file type
            return

        # Detect schema
        column_definitions = {}
        for column in df.columns:
            column_type = str(df[column].dtype)

            # Check for categorical data
            if column_type == 'object' and df[column].nunique() < len(df) * 0.5:
                column_type = 'category'

            column_definitions[column] = {
                'type': column_type,
                'sample_values': df[column].dropna().head(5).tolist()
            }


        # And when creating the schema:
        schema = SchemaDefinition.objects.create(
            data_source=datasource,
            column_definitions=json.loads(json.dumps(column_definitions, cls=CustomJSONEncoder)),
            row_count=len(df)
        )

        # Identify potential primary keys
        for column in df.columns:
            # Skip columns with NaN values
            if df[column].isna().any():
                continue

            # Calculate uniqueness ratio
            uniqueness = df[column].nunique() / len(df)

            # Only consider columns with high uniqueness (>80%)
            if uniqueness > 0.8:
                PrimaryKeyCandidate.objects.create(
                    schema=schema,
                    column_name=column,
                    uniqueness_ratio=uniqueness,
                    is_confirmed=False  # Needs user confirmation
                )

        # Check for relationships with existing sources
        find_related_sources(datasource)

        # Record this as the initial version
        SchemaChange.objects.create(
            source=datasource,
            change_type='initial',
            details={'columns': list(column_definitions.keys())}
        )

    except Exception as e:
        # Log the error and continue
        print(f"Error processing file: {e}")

def find_related_sources(datasource):
    """
    Find potentially related sources based on filename similarity and schema
    """
    # Skip if this is the first source
    if DataSource.objects.count() <= 1:
        return

    # Get the new source's schema
    new_schema = SchemaDefinition.objects.get(data_source=datasource)
    new_columns = set(new_schema.get_columns())

    # Look for existing sources with similar names or schemas
    existing_sources = DataSource.objects.exclude(pk=datasource.pk)

    for existing in existing_sources:
        try:
            existing_schema = SchemaDefinition.objects.get(data_source=existing)
            existing_columns = set(existing_schema.get_columns())

            # Calculate name similarity
            name_similarity = fuzz.ratio(datasource.original_filename, existing.original_filename) / 100

            # Calculate schema similarity
            common_columns = new_columns.intersection(existing_columns)
            schema_similarity = len(common_columns) / max(len(new_columns), len(existing_columns))

            # Overall similarity is a weighted combination
            similarity = (name_similarity * 0.4) + (schema_similarity * 0.6)

            # If similarity is above threshold, create a relationship
            if similarity > 0.5:
                relationship_type = 'version' if similarity > 0.8 else 'related'

                # Check if this might be a newer version
                if name_similarity > 0.7 and datasource.upload_date > existing.upload_date:
                    # Record changes between versions
                    added_columns = new_columns - existing_columns
                    removed_columns = existing_columns - new_columns

                    if added_columns:
                        SchemaChange.objects.create(
                            source=datasource,
                            previous_version=existing,
                            change_type='add_column',
                            details={'columns': list(added_columns)}
                        )

                    if removed_columns:
                        SchemaChange.objects.create(
                            source=datasource,
                            previous_version=existing,
                            change_type='remove_column',
                            details={'columns': list(removed_columns)}
                        )

                # Create relationship record
                SchemaRelationship.objects.create(
                    source_schema=existing_schema,
                    target_schema=new_schema,
                    relationship_type=relationship_type,
                    source_columns=list(common_columns),
                    target_columns=list(common_columns),
                    similarity_score=similarity
                )
        except SchemaDefinition.DoesNotExist:
            continue

def datasource_detail(request, pk):
    datasource = get_object_or_404(DataSource, pk=pk)

    try:
        schema = SchemaDefinition.objects.get(data_source=datasource)
        primary_keys = PrimaryKeyCandidate.objects.filter(schema=schema)
        changes = SchemaChange.objects.filter(source=datasource)

        # Get relationships
        outgoing = SchemaRelationship.objects.filter(source_schema=schema)
        incoming = SchemaRelationship.objects.filter(target_schema=schema)
        relationships = list(outgoing) + list(incoming)

    except SchemaDefinition.DoesNotExist:
        schema = None
        primary_keys = []
        changes = []
        relationships = []

    return render(request, 'tracker/datasource_detail.html', {
        'datasource': datasource,
        'schema': schema,
        'primary_keys': primary_keys,
        'changes': changes,
        'relationships': relationships,
        'title': f'Data Source: {datasource.original_filename}'
    })

def schema_list(request):
    schemas = SchemaDefinition.objects.all().order_by('-detected_date')
    return render(request, 'tracker/schema_list.html', {
        'schemas': schemas,
        'title': 'All Schemas'
    })

def compare_schemas(request, pk1, pk2):
    schema1 = get_object_or_404(SchemaDefinition, pk=pk1)
    schema2 = get_object_or_404(SchemaDefinition, pk=pk2)

    # Get column sets
    columns1 = set(schema1.get_columns())
    columns2 = set(schema2.get_columns())

    # Find common and different columns
    common_columns = columns1.intersection(columns2)
    only_in_schema1 = columns1 - columns2
    only_in_schema2 = columns2 - columns1

    # Find type differences in common columns
    type_differences = {}
    for column in common_columns:
        type1 = schema1.get_column_type(column)
        type2 = schema2.get_column_type(column)
        if type1 != type2:
            type_differences[column] = {
                'schema1_type': type1,
                'schema2_type': type2
            }

    return render(request, 'tracker/compare_schemas.html', {
        'schema1': schema1,
        'schema2': schema2,
        'common_columns': common_columns,
        'only_in_schema1': only_in_schema1,
        'only_in_schema2': only_in_schema2,
        'type_differences': type_differences,
        'title': 'Compare Schemas'
    })

class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        from decimal import Decimal
        import datetime

        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(obj, datetime.date):
            return obj.strftime('%Y-%m-%d')
        return super().default(obj)
