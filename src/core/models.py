from django.core.exceptions import ValidationError
from django.db import models

from phonenumber_field.modelfields import PhoneNumberField


class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=2, unique=True, help_text='ISO 3166-1 alpha-2')
    language = models.CharField(max_length=3, default='en', help_text='ISO 639-1', null=True, blank=True)
    currency = models.CharField(max_length=3, default='USD', help_text='ISO 4217', null=True, blank=True)
    phone_code = models.CharField(max_length=4, default='+1', help_text='e.g. +1', null=True, blank=True)

    is_services_available = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Countries'

    def __str__(self):
        return self.name


class Application(models.Model):
    name = models.CharField(max_length=100, help_text='Application name', default='Zaala Society')
    short_name = models.CharField(max_length=10, help_text='Your application short name', default='ZS')
    tagline = models.CharField(
        max_length=100, help_text='Your application business line', default='will be update it soon'
    )
    description = models.TextField(
        default="will be update it soon",
        help_text='Application description'
    )

    favicon = models.ImageField(
        upload_to='core/application/images', null=True, blank=True, help_text='Application favicon'
    )
    logo = models.ImageField(
        upload_to='core/application/images', null=True, blank=True,
        help_text='Application real colors logo'
    )
    logo_dark = models.ImageField(
        upload_to='core/application/images', null=True, blank=True, help_text='For dark theme only'
    )
    logo_light = models.ImageField(
        upload_to='core/application/images', null=True, blank=True, help_text='For light theme only'
    )

    contact_email1 = models.EmailField(
        max_length=100, default='support@zaalasociety.com', help_text='Application contact email 1'
    )
    contact_email2 = models.EmailField(
        max_length=100, default='support@zaalasociety.com', help_text='Application contact email 2'
    )
    contact_phone1 = PhoneNumberField(
        help_text='Application contact phone 1', default='+923029677678'
    )
    contact_phone2 = PhoneNumberField(
        help_text='Application contact phone 2', default='+923065953957'
    )

    address = models.CharField(
        max_length=255, help_text='office address', default='Mandian Abbottabad Near Comsats University'
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=6, help_text='latitude', default=23.7)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, help_text='longitude', default=90.3)

    terms_url = models.URLField(
        max_length=255, default='https://zaalasociety.com/terms-of-use/', help_text='Terms and Conditions page link'
    )

    version = models.CharField(max_length=10, help_text='Current version', default='1.0.0')
    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Application"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if Application.objects.exists() and not self.pk:
            raise ValidationError("Only one record allowed.")
        super(Application, self).save(*args, **kwargs)

class ContactMessage(models.Model):
    """
    Model to store contact form messages.
    """
    SUBJECT_CHOICES = [
        ('general', 'General Inquiry'),
        ('support', 'Customer Support'),
        ('feedback', 'Feedback'),
        ('order', 'Order Issue'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES, default='general')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject}"


class GalleryForm(models.Model):
    image = models.ImageField(upload_to='gallery/images', null=True, blank=True, help_text='Gallery Images')



