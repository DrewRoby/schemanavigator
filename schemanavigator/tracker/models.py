from django.db import models
from django.contrib.auth.models import User
import json

class DataSource(models.Model):
    """
    Represents a file that has been ingested into the system.
    """
    original_filename = models.CharField(max_length=255)
    upload_date = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='uploads/%Y/%m/%d/', null=True, blank=True)
    canonical_name = models.CharField(max_length=255)  # The "concept" name
    schema_version = models.IntegerField(default=1)
    source_type = models.CharField(max_length=20, choices=[
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
        ('other', 'Other')
    ], default='csv')

    def __str__(self):
        return f"{self.canonical_name} v{self.schema_version} ({self.original_filename})"

class SchemaDefinition(models.Model):
    """
    Stores the schema details of a data source.
    """
    data_source = models.OneToOneField(DataSource, on_delete=models.CASCADE, related_name='schema')
    detected_date = models.DateTimeField(auto_now_add=True)
    column_definitions = models.JSONField()  # Stores column names, types, etc.
    row_count = models.IntegerField(default=0)

    def __str__(self):
        return f"Schema for {self.data_source}"

    def get_columns(self):
        """Returns a list of column names"""
        return list(self.column_definitions.keys())

    def get_column_type(self, column_name):
        """Returns the type of a specific column"""
        return self.column_definitions.get(column_name, {}).get('type')

class PrimaryKeyCandidate(models.Model):
    """
    Stores potential primary keys identified in a schema.
    """
    schema = models.ForeignKey(SchemaDefinition, on_delete=models.CASCADE, related_name='primary_keys')
    column_name = models.CharField(max_length=255)
    uniqueness_ratio = models.FloatField()  # 1.0 means completely unique
    is_confirmed = models.BooleanField(default=False)  # User confirmed this is a PK

    def __str__(self):
        return f"{self.column_name} ({self.uniqueness_ratio*100:.1f}% unique)"

class SchemaChange(models.Model):
    """
    Records changes between schema versions.
    """
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name='changes')
    previous_version = models.ForeignKey(DataSource, on_delete=models.SET_NULL, null=True, related_name='next_changes')
    change_date = models.DateTimeField(auto_now_add=True)
    change_type = models.CharField(max_length=50, choices=[
        ('initial', 'Initial Version'),
        ('add_column', 'Add Column'),
        ('remove_column', 'Remove Column'),
        ('rename_column', 'Rename Column'),
        ('type_change', 'Column Type Change'),
        ('other', 'Other Change')
    ])
    details = models.JSONField()  # Details about what changed

    def __str__(self):
        if self.change_type == 'initial':
            return f"Initial schema for {self.source}"
        return f"{self.change_type} on {self.source}"

class SchemaRelationship(models.Model):
    """
    Records relationships between schemas/data sources.
    """
    source_schema = models.ForeignKey(SchemaDefinition, on_delete=models.CASCADE, related_name='outgoing_relationships')
    target_schema = models.ForeignKey(SchemaDefinition, on_delete=models.CASCADE, related_name='incoming_relationships')
    relationship_type = models.CharField(max_length=50, choices=[
        ('version', 'Version Change'),
        ('related', 'Related Data'),
        ('derived', 'Derived Data'),
        ('other', 'Other Relationship')
    ])
    source_columns = models.JSONField(null=True, blank=True)  # Columns in source involved in relationship
    target_columns = models.JSONField(null=True, blank=True)  # Columns in target involved in relationship
    similarity_score = models.FloatField(default=0.0)  # How similar are the schemas (0.0-1.0)

    def __str__(self):
        return f"{self.source_schema} -> {self.target_schema} ({self.relationship_type})"