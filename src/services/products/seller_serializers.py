import re
from rest_framework import serializers
from django.contrib.auth.models import User
from .seller_models import Seller, SellerStore, OnlineSellerProfile, PhysicalSellerProfile


class OnlineSellerRegisterSerializer(serializers.Serializer):
    # User fields
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    # Seller fields
    store_name = serializers.CharField(max_length=200)
    owner_name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=20)
    city = serializers.CharField(max_length=100)

    # Online-specific
    business_type = serializers.CharField(max_length=50)
    product_category = serializers.CharField(max_length=100)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        pattern = r'^03\d{2}-\d{7}$'
        if not re.match(pattern, value):
            raise serializers.ValidationError("Phone must be in format: 03XX-XXXXXXX")
        
        from .models import Store
        if Store.objects.filter(phone=value).exists():
             raise serializers.ValidationError("A store with this phone number already exists.")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data


class PhysicalSellerRegisterSerializer(serializers.Serializer):
    # User fields
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    # Seller fields
    store_name = serializers.CharField(max_length=200)
    owner_name = serializers.CharField(max_length=200)
    phone = serializers.CharField(max_length=20)
    city = serializers.CharField(max_length=100)

    # Physical-specific
    cnic = serializers.CharField(max_length=15)
    full_address = serializers.CharField()
    opening_hours = serializers.CharField(max_length=100)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        pattern = r'^03\d{2}-\d{7}$'
        if not re.match(pattern, value):
            raise serializers.ValidationError("Phone must be in format: 03XX-XXXXXXX")
        
        from .models import Store
        if Store.objects.filter(phone=value).exists():
             raise serializers.ValidationError("A store with this phone number already exists.")
        return value

    def validate_cnic(self, value):
        pattern = r'^\d{5}-\d{7}-\d{1}$'
        if not re.match(pattern, value):
            raise serializers.ValidationError("CNIC must be in format: XXXXX-XXXXXXX-X")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data
