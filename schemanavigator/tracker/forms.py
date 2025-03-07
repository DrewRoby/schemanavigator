from django import forms
from .models import DataSource

class DataSourceUploadForm(forms.ModelForm):
    file = forms.FileField(widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))
    canonical_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="A name to identify this type of data across versions"
    )

    class Meta:
        model = DataSource
        fields = ['file', 'canonical_name', 'source_type']
        widgets = {
            'source_type': forms.Select(attrs={'class': 'form-select'})
        }