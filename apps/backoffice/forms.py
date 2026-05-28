from django import forms
from apps.markets.models import Event

class EventCreateForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'sport', 'starts_at']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Real Madrid vs Barcelona'
            }),
            'sport': forms.Select(attrs={
                'class': 'form-control',
            }),
            'starts_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }
