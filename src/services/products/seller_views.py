from django.db import transaction
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.authtoken.models import Token
from rest_framework import status

from .seller_models import Seller, SellerStore, OnlineSellerProfile, PhysicalSellerProfile
from .seller_serializers import OnlineSellerRegisterSerializer, PhysicalSellerRegisterSerializer


class RegisterOnlineSellerView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = OnlineSellerRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            # Create User
            username = data['email'].split('@')[0]
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=data['email'],
                password=data['password'],
                first_name=data['owner_name'].split(' ')[0],
                last_name=' '.join(data['owner_name'].split(' ')[1:]) if len(data['owner_name'].split(' ')) > 1 else '',
            )

            # Create Seller
            seller = Seller.objects.create(
                user=user,
                seller_type='online',
                store_name=data['store_name'],
                owner_name=data['owner_name'],
                phone=data['phone'],
                city=data['city'],
            )

            # Create SellerStore
            seller_store = SellerStore.objects.create(
                seller=seller,
                name=data['store_name'],
                city=data['city'],
                phone=data['phone'],
            )

            # Create public Store
            from .models import Store
            p_store, _ = Store.objects.get_or_create(
                name=data['store_name'],
                defaults={
                    'city': data['city'],
                    'phone': data['phone'],
                    'address': '',
                    'seller': seller,
                }
            )
            if not p_store.seller:
                p_store.seller = seller
                p_store.save()

            # Create OnlineSellerProfile
            OnlineSellerProfile.objects.create(
                seller=seller,
                business_type=data['business_type'],
                product_category=data['product_category'],
            )

            # Create token for auto-login
            Token.objects.filter(user=user).delete()
            token = Token.objects.create(user=user)

            # ── Send welcome email asynchronously ──────────────────────────
            try:
                from src.api.email_service import send_welcome_email
                send_welcome_email(user)
            except Exception as _email_err:
                import logging
                logging.getLogger(__name__).error(f'[EMAIL] Seller welcome email failed: {_email_err}')
            # ──────────────────────────────────────────────────────────────

            return Response({
                'token': token.key,
                'store_name': seller.store_name,
                'user_id': user.id,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': data['owner_name'],
                    'seller_type': 'online',
                },
                'message': 'Online seller account created successfully!'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            raise e


class RegisterPhysicalSellerView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = PhysicalSellerRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            # Create User
            username = data['email'].split('@')[0]
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=data['email'],
                password=data['password'],
                first_name=data['owner_name'].split(' ')[0],
                last_name=' '.join(data['owner_name'].split(' ')[1:]) if len(data['owner_name'].split(' ')) > 1 else '',
            )

            # Create Seller
            seller = Seller.objects.create(
                user=user,
                seller_type='physical',
                store_name=data['store_name'],
                owner_name=data['owner_name'],
                phone=data['phone'],
                city=data['city'],
            )

            # Create SellerStore
            seller_store = SellerStore.objects.create(
                seller=seller,
                name=data['store_name'],
                city=data['city'],
                address=data['full_address'],
                phone=data['phone'],
                opening_hours=data['opening_hours'],
            )

            # Create public Store
            from .models import Store
            p_store, _ = Store.objects.get_or_create(
                name=data['store_name'],
                defaults={
                    'city': data['city'],
                    'address': data['full_address'],
                    'phone': data['phone'],
                    'status': 'Open',
                    'seller': seller,
                }
            )
            if not p_store.seller:
                p_store.seller = seller
                p_store.save()

            # Create PhysicalSellerProfile
            PhysicalSellerProfile.objects.create(
                seller=seller,
                cnic=data['cnic'],
                full_address=data['full_address'],
                opening_hours=data['opening_hours'],
            )

            Token.objects.filter(user=user).delete()
            token = Token.objects.create(user=user)

            # ── Send welcome email asynchronously ──────────────────────────
            try:
                from src.api.email_service import send_welcome_email
                send_welcome_email(user)
            except Exception as _email_err:
                import logging
                logging.getLogger(__name__).error(f'[EMAIL] Seller welcome email failed: {_email_err}')
            # ──────────────────────────────────────────────────────────────

            return Response({
                'token': token.key,
                'store_name': seller.store_name,
                'user_id': user.id,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': data['owner_name'],
                    'seller_type': 'physical',
                },
                'message': 'Physical seller account created successfully!'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            raise e


@api_view(['GET'])
@permission_classes([AllowAny])
def check_email(request):
    email = request.query_params.get('email', '')
    exists = User.objects.filter(email=email).exists()
    return Response({'exists': exists})
