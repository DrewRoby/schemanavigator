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

            # Check for similar existing files to avoid duplication
            similar_sources = DataSource.objects.filter(
                original_filename=datasource.original_filename,
                canonical_name=datasource.canonical_name,
                source_type=datasource.source_type
            ).exclude(pk=datasource.pk)

            if similar_sources.exists():
                # Use the most recent similar source
                similar_source = similar_sources.order_by('-upload_date').first()
                messages.info(request, f'Using existing source "{similar_source.original_filename}" '
                                       f'(v{similar_source.schema_version}) instead of creating a duplicate')

                # Delete the new datasource since we're using an existing one
                datasource.delete()
                return redirect('datasource_detail', pk=similar_source.pk)

            # Get additional processing options
            file_type = datasource.source_type

            # Process the file based on the type and options
            success = False

            if file_type == 'csv':
                delimiter_preset = request.POST.get('delimiter_preset', 'comma')
                delimiter = ','  # Default

                if delimiter_preset == 'tab':
                    delimiter = '\t'
                elif delimiter_preset == 'semicolon':
                    delimiter = ';'
                elif delimiter_preset == 'pipe':
                    delimiter = '|'
                elif delimiter_preset == 'custom':
                    custom_delimiter = request.POST.get('delimiter_custom', '')
                    if custom_delimiter:
                        delimiter = custom_delimiter

                encoding = request.POST.get('encoding', 'utf-8')
                success = process_csv_file(datasource, delimiter=delimiter, encoding=encoding)

            elif file_type == 'excel':
                sheet_name = request.POST.get('sheet_name', '')
                # If sheet_name is a number, convert to int
                if sheet_name and sheet_name.isdigit():
                    sheet_name = int(sheet_name)
                # If empty, set to 0 (first sheet)
                elif not sheet_name:
                    sheet_name = 0

                success = process_excel_file(datasource, sheet_name=sheet_name)

            elif file_type == 'json':
                encoding = request.POST.get('encoding', 'utf-8')
                success = process_json_file(datasource, encoding=encoding)

            else:
                # Default processing
                success = process_file(datasource)

            if success:
                messages.success(request, f'File "{datasource.original_filename}" successfully uploaded and schema detected!')
                return redirect('datasource_detail', pk=datasource.pk)
            else:
                messages.error(request, f'Error processing file "{datasource.original_filename}"')
                # Clean up the datasource since we couldn't process it
                datasource.delete()
    else:
        form = DataSourceUploadForm()

    return render(request, 'tracker/upload_modified.html', {
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
            return process_excel_file(datasource)
        elif file_extension.lower() == '.csv':
            return process_csv_file(datasource)
        elif file_extension.lower() == '.json':
            return process_json_file(datasource)
        else:
            # Unsupported file type
            return False
    except Exception as e:
        # Log the error and continue
        print(f"Error processing file: {e}")
        return False

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

def retry_detection(request, pk):
    datasource = get_object_or_404(DataSource, pk=pk)

    if request.method == 'POST':
        file_type = request.POST.get('file_type')

        # Update the data source type
        datasource.source_type = file_type
        datasource.save()

        # Process based on file type
        if file_type == 'csv':
            # Get delimiter
            delimiter_preset = request.POST.get('delimiter_preset')
            delimiter = ','  # Default

            if delimiter_preset == 'tab':
                delimiter = '\t'
            elif delimiter_preset == 'semicolon':
                delimiter = ';'
            elif delimiter_preset == 'pipe':
                delimiter = '|'
            elif delimiter_preset == 'custom':
                custom_delimiter = request.POST.get('delimiter_custom')
                if custom_delimiter:
                    delimiter = custom_delimiter

            encoding = request.POST.get('encoding', 'utf-8')

            # Call function to process CSV with specific delimiter
            success = process_csv_file(datasource, delimiter=delimiter, encoding=encoding)

        elif file_type == 'excel':
            sheet_name = request.POST.get('sheet_name')
            # If sheet_name is a number, convert to int
            if sheet_name and sheet_name.isdigit():
                sheet_name = int(sheet_name)
            # If empty, set to 0 (first sheet)
            elif not sheet_name:
                sheet_name = 0

            success = process_excel_file(datasource, sheet_name=sheet_name)

        elif file_type == 'json':
            encoding = request.POST.get('encoding', 'utf-8')
            success = process_json_file(datasource, encoding=encoding)

        else:
            # Generic processing
            success = process_file(datasource)

        if success:
            messages.success(request, f'Successfully detected schema for {datasource.original_filename}')
        else:
            messages.error(request, f'Failed to detect schema for {datasource.original_filename}')

    return redirect('datasource_detail', pk=datasource.pk)

def process_csv_file(datasource, delimiter=',', encoding='utf-8'):
    """Process a CSV file with specific delimiter and encoding"""
    try:
        file_path = datasource.file.path
        print(f"Processing CSV file: {file_path}")
        print(f"Using delimiter: '{delimiter}' and encoding: {encoding}")

        # Try to read with pandas
        df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding, engine='python')
        print(f"CSV read successful. Columns: {df.columns.tolist()}")
        print(f"Found {len(df)} rows")

        return create_schema_from_dataframe(df, datasource)
    except Exception as e:
        print(f"Error processing CSV file: {e}")
        # Try with different engine as fallback
        try:
            print("Trying with C engine instead...")
            df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding, engine='c')
            return create_schema_from_dataframe(df, datasource)
        except Exception as e2:
            print(f"Second attempt failed: {e2}")
            return False

def process_excel_file(datasource, sheet_name=0):
    """Process an Excel file with specific sheet"""
    try:
        file_path = datasource.file.path
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        return create_schema_from_dataframe(df, datasource)
    except Exception as e:
        print(f"Error processing Excel file: {e}")
        return False

def process_json_file(datasource, encoding='utf-8'):
    """Process a JSON file"""
    try:
        file_path = datasource.file.path
        with open(file_path, 'r', encoding=encoding) as f:
            data = json.load(f)

        # Convert to dataframe - this handles different JSON structures
        if isinstance(data, list):
            # List of records
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # Try to convert dictionary to dataframe
            if all(isinstance(data[key], (list, dict)) for key in data):
                # Nested structure - flatten first level
                flattened = {}
                for key, value in data.items():
                    if isinstance(value, list):
                        flattened[key] = value
                    elif isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            flattened[f"{key}_{subkey}"] = subvalue
                df = pd.DataFrame(flattened)
            else:
                # Simple dict
                df = pd.DataFrame([data])
        else:
            # Unsupported JSON structure
            return False

        return create_schema_from_dataframe(df, datasource)
    except Exception as e:
        print(f"Error processing JSON file: {e}")
        return False

def create_schema_from_dataframe(df, datasource):
    """Create schema definition from a pandas DataFrame"""
    try:
        # Remove any existing schema (in case this is a retry)
        try:
            old_schema = SchemaDefinition.objects.get(data_source=datasource)

            # Remove related primary key candidates
            PrimaryKeyCandidate.objects.filter(schema=old_schema).delete()

            # Remove the schema itself
            old_schema.delete()
        except SchemaDefinition.DoesNotExist:
            pass

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

        # Create schema definition
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

        return True
    except Exception as e:
        print(f"Error creating schema from DataFrame: {e}")
        return False

def file_preview(request, pk):
    """Get a preview of the file content with specified encoding and options"""
    datasource = get_object_or_404(DataSource, pk=pk)

    # Get parameters from request
    file_type = request.GET.get('file_type', datasource.source_type)
    encoding = request.GET.get('encoding', 'utf-8')
    delimiter = request.GET.get('delimiter', ',')
    sheet_name = request.GET.get('sheet_name', 0)

    # Handle tab delimiter special case
    if delimiter == 'tab':
        delimiter = '\t'

    preview_text = "Unable to generate preview"
    response_data = {'preview': preview_text}

    try:
        file_path = datasource.file.path

        if file_type == 'csv':
            # Read as text file for preview
            with open(file_path, 'r', encoding=encoding) as f:
                lines = [line.strip() for line in f.readlines()[:10]]
                preview_text = '\n'.join(lines)

            # Also provide the delimiter used for the client-side parser
            response_data['delimiter'] = delimiter

            # Try to also parse as a DataFrame for table data
            try:
                df = pd.read_csv(file_path, delimiter=delimiter, encoding=encoding, nrows=10, engine='python')
                # Convert DataFrame to a simple format for the table view
                response_data['table_data'] = {
                    'headers': df.columns.tolist(),
                    'rows': df.values.tolist()
                }
            except Exception as csv_e:
                print(f"Error parsing CSV as DataFrame: {str(csv_e)}")
                # If DataFrame parsing fails, the raw preview will still be available

        elif file_type == 'excel':
            # Use pandas to read Excel file
            try:
                # Convert sheet_name to int if it's a digit
                if sheet_name and sheet_name.isdigit():
                    sheet_name = int(sheet_name)
                # If empty, set to 0 (first sheet)
                elif not sheet_name:
                    sheet_name = 0

                df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=10)
                preview_text = df.to_string(index=False)

                # Also provide table data
                response_data['table_data'] = {
                    'headers': df.columns.tolist(),
                    'rows': df.values.tolist()
                }
            except Exception as e:
                preview_text = f"Error reading Excel file: {str(e)}"

        elif file_type == 'json':
            # Read JSON and format nicely
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    data = json.load(f)
                    # Format JSON with indentation for readability
                    preview_text = json.dumps(data, indent=2)
                    # Limit to reasonable size for preview
                    if len(preview_text) > 2000:
                        preview_text = preview_text[:2000] + "...\n[truncated]"

                    # Try to convert to DataFrame if it's a list of objects
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                        try:
                            df = pd.DataFrame(data[:10])  # Limit to 10 rows
                            response_data['table_data'] = {
                                'headers': df.columns.tolist(),
                                'rows': df.values.tolist()
                            }
                        except Exception as json_df_e:
                            print(f"Error converting JSON to DataFrame: {str(json_df_e)}")
            except Exception as e:
                preview_text = f"Error reading JSON file: {str(e)}"

        else:
            # Generic text preview
            with open(file_path, 'r', encoding=encoding) as f:
                lines = [line.strip() for line in f.readlines()[:10]]
                preview_text = '\n'.join(lines)

    except Exception as e:
        preview_text = f"Error generating preview: {str(e)}"

    # Update the preview text in the response
    response_data['preview'] = preview_text

    return JsonResponse(response_data)

def reanalyze_file(request, pk):
    """Show file preview and options for re-analyzing a file"""
    datasource = get_object_or_404(DataSource, pk=pk)

    return render(request, 'tracker/file_preview.html', {
        'datasource': datasource,
        'title': f'Re-analyze: {datasource.original_filename}'
    })

def reprocess_file(request, pk):
    """Re-process a file with specified options"""
    datasource = get_object_or_404(DataSource, pk=pk)

    if request.method == 'POST':
        # Get form parameters
        file_type = request.POST.get('file_type')
        create_new_version = request.POST.get('create_new_version') == 'on'

        # Check if a schema already exists for this datasource
        try:
            existing_schema = SchemaDefinition.objects.get(data_source=datasource)
            schema_exists = True
        except SchemaDefinition.DoesNotExist:
            schema_exists = False

        # Determine if we need a new version
        if schema_exists and create_new_version:
            # First check if we have an identical datasource already
            similar_sources = DataSource.objects.filter(
                original_filename=datasource.original_filename,
                canonical_name=datasource.canonical_name,
                source_type=file_type
            ).exclude(pk=datasource.pk)

            # If we found similar sources, don't create a duplicate
            if similar_sources.exists():
                # Use the most recent similar source
                similar_source = similar_sources.order_by('-upload_date').first()
                messages.info(request, f'Using existing source "{similar_source.original_filename}" '
                                       f'(v{similar_source.schema_version}) instead of creating a duplicate')
                return redirect('datasource_detail', pk=similar_source.pk)

            # Create a new version of the datasource
            new_datasource = DataSource.objects.create(
                original_filename=datasource.original_filename,
                file=datasource.file,
                canonical_name=datasource.canonical_name,
                schema_version=datasource.schema_version + 1,
                source_type=file_type
            )

            # Store the target datasource for processing
            target_datasource = new_datasource
        else:
            # Update the current datasource's source type
            datasource.source_type = file_type
            datasource.save()

            # Use the current datasource for processing
            target_datasource = datasource

            # If a schema exists, remove it for reprocessing
            if schema_exists:
                # Remove related primary key candidates
                PrimaryKeyCandidate.objects.filter(schema=existing_schema).delete()

                # Remove the schema itself
                existing_schema.delete()

        # Process based on file type
        if file_type == 'csv':
            # Get delimiter
            delimiter_preset = request.POST.get('delimiter_preset')
            delimiter = ','  # Default

            if delimiter_preset == 'tab':
                delimiter = '\t'
            elif delimiter_preset == 'semicolon':
                delimiter = ';'
            elif delimiter_preset == 'pipe':
                delimiter = '|'
            elif delimiter_preset == 'custom':
                custom_delimiter = request.POST.get('delimiter_custom')
                if custom_delimiter:
                    delimiter = custom_delimiter

            encoding = request.POST.get('encoding', 'utf-8')

            # Call function to process CSV with specific delimiter
            success = process_csv_file(target_datasource, delimiter=delimiter, encoding=encoding)

        elif file_type == 'excel':
            sheet_name = request.POST.get('sheet_name')
            # If sheet_name is a number, convert to int
            if sheet_name and sheet_name.isdigit():
                sheet_name = int(sheet_name)
            # If empty, set to 0 (first sheet)
            elif not sheet_name:
                sheet_name = 0

            success = process_excel_file(target_datasource, sheet_name=sheet_name)

        elif file_type == 'json':
            encoding = request.POST.get('encoding', 'utf-8')
            success = process_json_file(target_datasource, encoding=encoding)

        else:
            # Generic processing
            success = process_file(target_datasource)

        if success:
            if target_datasource.pk != datasource.pk:
                messages.success(request, f'Created new schema version (v{target_datasource.schema_version}) '
                                          f'for {target_datasource.original_filename}')
            else:
                messages.success(request, f'Successfully re-analyzed {target_datasource.original_filename}')
            return redirect('datasource_detail', pk=target_datasource.pk)
        else:
            if target_datasource.pk != datasource.pk:
                # If processing failed and we created a new datasource, delete it
                target_datasource.delete()
                messages.error(request, f'Failed to create new schema version for {datasource.original_filename}')
            else:
                messages.error(request, f'Failed to re-analyze {datasource.original_filename}')

    # Redirect back to the datasource detail
    return redirect('datasource_detail', pk=datasource.pk)
def delete_datasource(request, pk):
    """Delete a datasource and its associated schema"""
    datasource = get_object_or_404(DataSource, pk=pk)

    if request.method == 'POST':
        original_filename = datasource.original_filename

        # Delete the datasource (this will cascade to schema, primary keys, etc.)
        datasource.delete()

        messages.success(request, f'Successfully deleted "{original_filename}"')

    return redirect('schema_list')


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
