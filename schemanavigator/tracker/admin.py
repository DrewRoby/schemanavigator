from django.contrib import admin
from .models import DataSource, SchemaDefinition, PrimaryKeyCandidate, SchemaChange, SchemaRelationship

@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'canonical_name', 'schema_version', 'upload_date')
    search_fields = ('original_filename', 'canonical_name')
    list_filter = ('source_type', 'upload_date')

@admin.register(SchemaDefinition)
class SchemaDefinitionAdmin(admin.ModelAdmin):
    list_display = ('data_source', 'detected_date', 'row_count')
    search_fields = ('data_source__original_filename', 'data_source__canonical_name')

@admin.register(PrimaryKeyCandidate)
class PrimaryKeyCandidateAdmin(admin.ModelAdmin):
    list_display = ('column_name', 'schema', 'uniqueness_ratio', 'is_confirmed')
    list_filter = ('is_confirmed',)
    search_fields = ('column_name', 'schema__data_source__original_filename')

@admin.register(SchemaChange)
class SchemaChangeAdmin(admin.ModelAdmin):
    list_display = ('source', 'change_type', 'change_date')
    list_filter = ('change_type', 'change_date')
    search_fields = ('source__original_filename', 'source__canonical_name')

@admin.register(SchemaRelationship)
class SchemaRelationshipAdmin(admin.ModelAdmin):
    list_display = ('source_schema', 'target_schema', 'relationship_type', 'similarity_score')
    list_filter = ('relationship_type',)
    search_fields = ('source_schema__data_source__original_filename', 'target_schema__data_source__original_filename')