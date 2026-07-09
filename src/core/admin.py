from django.contrib import admin

# from .models import (
#     Country, Application, GalleryForm
# )


# @admin.register(Application)
# class ApplicationAdmin(admin.ModelAdmin):
#     list_display = ('name', 'short_name', 'tagline', 'is_active', 'created_on')


# @admin.register(Country)
# class CountryAdmin(admin.ModelAdmin):
#     list_display = ('name', 'short_name', 'language', 'currency', 'phone_code', 'is_active', 'created_on')


# @admin.register(GalleryForm)
# class GalleryAdmin(admin.ModelAdmin):
#     list_display = ('image',)
    
# from .models import ContactMessage

# @admin.register(ContactMessage)
# class ContactMessageAdmin(admin.ModelAdmin):
#     list_display = ('name', 'email', 'subject', 'created_at')
#     search_fields = ('name', 'email', 'subject')
#     list_filter = ('subject', 'created_at')

# Unregister unnecessary apps
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialAccount, SocialToken, SocialApp
from allauth.account.models import EmailAddress

admin.site.unregister(Group)
admin.site.unregister(Site)
admin.site.unregister(SocialAccount)
admin.site.unregister(SocialToken)
admin.site.unregister(SocialApp)
admin.site.unregister(EmailAddress)

from rest_framework.authtoken.models import Token, TokenProxy
try:
    admin.site.unregister(Token)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(TokenProxy)
except admin.sites.NotRegistered:
    pass


