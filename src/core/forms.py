from django import forms
from .models import ContactMessage

class ContactForm(forms.ModelForm):
    """
    Django form for Contact Message submission.
    """
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Name*', 'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email*', 'class': 'form-control'}),
            'subject': forms.Select(choices=ContactMessage.SUBJECT_CHOICES, attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'placeholder': 'Write Message Here', 'class': 'form-control'}),
        }
