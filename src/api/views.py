from django.shortcuts import render, redirect
from django.contrib import messages
from rest_framework import generics, viewsets, permissions
from django.db.models import Q, Case, When, F
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from datetime import date, datetime
from django.core.cache import cache

from ..core.forms import ContactForm
from ..core.models import ContactMessage
from ..services.products.models import Product, Store, StoreLocation, ProductLocation, Category, ShoppingList, ShoppingListItem
from .serializers import (
    ContactMessageSerializer, ProductSerializer, StoreSerializer,
    StoreLocationSerializer,  CategorySerializer,ShoppingListSerializer
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

# ─── Rate Limiting Helpers ────────────────────────────────────────────────────
_RATE_LIMIT_MAX_ATTEMPTS = 5       # max failed attempts
_RATE_LIMIT_WINDOW_SECONDS = 900   # 15-minute window

def _get_client_ip(request):
    """Return the best-available client IP address from the request."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')

def _is_rate_limited(cache_key):
    """Return True if the IP has exceeded the allowed failed-attempt threshold."""
    attempts = cache.get(cache_key, 0)
    return attempts >= _RATE_LIMIT_MAX_ATTEMPTS

def _record_failed_attempt(cache_key):
    """Increment the failed-attempt counter, setting the TTL on first attempt."""
    attempts = cache.get(cache_key, 0)
    cache.set(cache_key, attempts + 1, timeout=_RATE_LIMIT_WINDOW_SECONDS)

def _clear_rate_limit(cache_key):
    """Reset the counter after a successful login."""
    cache.delete(cache_key)
# ─────────────────────────────────────────────────────────────────────────────

# ✅ Contact Form View
def contact_view(request):
    """Handles the contact form submission."""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Your message has been sent successfully!")
            return redirect('contact')
    else:
        form = ContactForm()

    return render(request, 'contact.html', {'form': form})


def send_contact_notification(name, email, subject, message):
    from django.core.mail import EmailMultiAlternatives
    import os
    try:
        admin_email = os.environ.get('ADMIN_EMAIL', os.environ.get('BREVO_SMTP_LOGIN'))
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #2E7D32; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0;">Gro.Nav</h1>
                <p style="color: #C8E6C9; margin: 5px 0;">New Contact Form Message</p>
            </div>
            <div style="padding: 30px; background-color: #f9f9f9;">
                <h2 style="color: #2E7D32;">New Message Received</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd; background: #E8F5E9; font-weight: bold; width: 30%;">Name</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd; background: #E8F5E9; font-weight: bold;">Email</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{email}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd; background: #E8F5E9; font-weight: bold;">Subject</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{subject}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd; background: #E8F5E9; font-weight: bold;">Message</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{message}</td>
                    </tr>
                </table>
                <p style="margin-top: 20px; color: #666;">
                    Reply directly to: <a href="mailto:{email}" style="color: #2E7D32;">{email}</a>
                </p>
            </div>
            <div style="background-color: #2E7D32; padding: 15px; text-align: center;">
                <p style="color: #C8E6C9; margin: 0; font-size: 12px;">Gro.Nav — Pakistan's Smart Grocery Comparison Platform</p>
            </div>
        </div>
        """
        
        msg = EmailMultiAlternatives(
            subject=f"[Gro.Nav Contact] {subject} — from {name}",
            body=f"New contact message from {name} ({email})\n\nSubject: {subject}\n\nMessage:\n{message}",
            from_email=os.environ.get('DEFAULT_FROM_EMAIL', 'Gro.Nav <noreply@gronav.com>'),
            to=[admin_email],
            reply_to=[email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        print(f"Contact notification sent to admin for message from {name}")
    except Exception as e:
        print(f"Contact email error: {e}")

# ✅ API Views for Contact Messages
class ContactMessageListCreateAPIView(generics.ListCreateAPIView):
    queryset = ContactMessage.objects.all()
    serializer_class = ContactMessageSerializer

    def perform_create(self, serializer):
        instance = serializer.save()
        try:
            from threading import Thread
            name = instance.name
            email = instance.email
            subject = instance.subject
            message = instance.message
            Thread(target=send_contact_notification, args=(name, email, subject, message)).start()
        except Exception as e:
            print(f"Error starting contact email thread: {e}")


from rest_framework.pagination import PageNumberPagination

class ProductPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class ProductListView(generics.ListAPIView):

    serializer_class = ProductSerializer
    pagination_class = ProductPagination

    def get_queryset(self):
        from django.db.models import Subquery, OuterRef, Count, Avg
        from django.db.models.functions import Coalesce
        from ..services.products.models import ProductRating, ProductView

        ratings_avg = ProductRating.objects.filter(product=OuterRef('pk')).values('product').annotate(avg=Avg('rating')).values('avg')
        ratings_count = ProductRating.objects.filter(product=OuterRef('pk')).values('product').annotate(count=Count('id')).values('count')
        views_count = ProductView.objects.filter(product=OuterRef('pk')).values('product').annotate(count=Count('id')).values('count')

        queryset = Product.objects.select_related(
            'category', 'store'
        ).annotate(
            avg_rating=Coalesce(Subquery(ratings_avg), 0.0),
            review_count=Coalesce(Subquery(ratings_count), 0),
            total_views=Coalesce(Subquery(views_count), 0)
        ).order_by(
            '-avg_rating',
            '-review_count',
            '-created_at'
        )

        search_query = self.request.query_params.get('search')
        category = self.request.query_params.get('category')
        store = self.request.query_params.get('store')
        city = self.request.query_params.get('city')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')

        if city:
            queryset = queryset.filter(store__city__iexact=city)
        if category:
            if str(category).isdigit():
                queryset = queryset.filter(category_id=category)
            else:
                queryset = queryset.filter(category__name__iexact=category)
        if store:
            if str(store).isdigit():
                queryset = queryset.filter(store_id=store)
            else:
                queryset = queryset.filter(store__name__iexact=store)
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(category__name__icontains=search_query) |
                Q(store__name__icontains=search_query)
            )
        return queryset


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.filter(products__isnull=False).distinct()
    serializer_class = CategorySerializer

class CityListView(generics.GenericAPIView):
    def get(self, request):
        cities = Store.objects.values_list('city', flat=True).distinct()
        cities = [city for city in cities if city] # Filter out empty
        return Response(cities)


class StoreListAPIView(generics.ListAPIView):
    """API view to retrieve a list of stores."""
    serializer_class = StoreSerializer

    def get_queryset(self):
        from django.db.models import Avg, Count
        return Store.objects.annotate(
            avg_rating=Avg('storerating__rating'),
            review_count=Count('storerating')
        ).order_by(
            '-avg_rating',
            '-review_count',
            '-created_at'
        )




class StoreDetailAPIView(generics.RetrieveAPIView):
    """API view to retrieve a single store's details."""
    queryset = Store.objects.all()
    serializer_class = StoreSerializer


class StoreLocationListAPIView(generics.ListAPIView):
    """API view to retrieve a list of store locations."""
    queryset = StoreLocation.objects.all()
    serializer_class = StoreLocationSerializer


# ✅ Get Store Location for Category
def get_category_location(request, category_name):
    """Retrieve store location of the first product in a given category."""
    products = Product.objects.filter(category__name=category_name)

    if not products.exists():
        return JsonResponse({"error": "Category not found"}, status=400)

    first_product = products.first()
    location = ProductLocation.objects.filter(product=first_product).first()

    if not location:
        return JsonResponse({"error": "Location not found for this category"}, status=400)

    return JsonResponse({
        "lat": location.store_location.lat,
        "lng": location.store_location.lng,
        "category": category_name
    })


# ✅ Save Shopping List API
@api_view(["POST"])
@permission_classes([AllowAny])  # Keep it open, but manually authenticate
def save_shopping_list(request):
    print("🔹 Received Data:", request.data)

    try:
        cart_items = request.data.get("items", [])
        if not cart_items:
            return Response({"error": "Cart is empty", "received_data": request.data}, status=400)

        # ✅ Manually extract user from token
        auth = TokenAuthentication()
        try:
            user_auth_tuple = auth.authenticate(request)
            if not user_auth_tuple:
                raise AuthenticationFailed("Invalid token")
            user = user_auth_tuple[0]  # ✅ Get the authenticated user
        except AuthenticationFailed:
            return Response({"error": "Invalid or missing token"}, status=401)

        print("✅ Authenticated User:", user)

        # ✅ Now, the shopping list is correctly linked to the user
        shopping_list = ShoppingList.objects.create(user=user)

        for item in cart_items:
            try:
                product = get_object_or_404(Product, id=item["product_id"])
                ShoppingListItem.objects.create(
                    shopping_list=shopping_list,
                    product=product,
                    quantity=item.get("quantity", 1)
                )
            except Exception as e:
                print(f"⚠️ Error with product {item['product_id']}: {str(e)}")
                return Response({"error": f"Product issue: {str(e)}"}, status=400)

        return Response({"message": "Shopping list saved successfully!"}, status=201)

    except Exception as e:
        print(f"❌ Critical Error: {str(e)}")
        return Response({"error": f"Unexpected error: {str(e)}"}, status=400)
    

from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

class UserShoppingListView(APIView):
    def get(self, request):
        # Manually extract user from token
        auth = TokenAuthentication()
        try:
            user_auth_tuple = auth.authenticate(request)
            if not user_auth_tuple:
                raise AuthenticationFailed("Invalid token")
            request.user = user_auth_tuple[0]
        except AuthenticationFailed:
            return Response({"error": "Invalid or missing token"}, status=401)

        # Fetch shopping lists for the logged-in user
        shopping_lists = ShoppingList.objects.filter(user=request.user)

        # Include shopping list items and product details
        data = []
        for shopping_list in shopping_lists:
            items = ShoppingListItem.objects.filter(shopping_list=shopping_list).select_related("product")
            
            # Serialize shopping list items
            item_data = [
                {
                    "product": {
                        "id": item.product.id,
                        "name": item.product.name,
                        "image": item.product.image.url if item.product.image else None,
                        "price": item.product.price,
                        "category": item.product.category.name if item.product.category else "Unknown",
                    },
                    "quantity": item.quantity
                }
                for item in items
            ]

            data.append({
                "id": shopping_list.id,
                "created_at": shopping_list.created_at,
                "items": item_data,  # ✅ Now includes product details
            })

        return Response(data, status=200)


def get_categories(request):
    store_id = request.GET.get('store_id')
    categories = Category.objects.filter(products__store__id=store_id).distinct().values('id', 'name')
    return JsonResponse(list(categories), safe=False)


class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all().order_by('-updated_at', '-id')
    serializer_class = StoreSerializer
    permission_classes = [IsAuthenticated]


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Subquery, OuterRef, Count, Avg
        from django.db.models.functions import Coalesce
        from ..services.products.models import ProductRating, ProductView

        ratings_avg = ProductRating.objects.filter(product=OuterRef('pk')).values('product').annotate(avg=Avg('rating')).values('avg')
        ratings_count = ProductRating.objects.filter(product=OuterRef('pk')).values('product').annotate(count=Count('id')).values('count')
        views_count = ProductView.objects.filter(product=OuterRef('pk')).values('product').annotate(count=Count('id')).values('count')

        queryset = Product.objects.select_related('store', 'category').annotate(
            avg_rating=Coalesce(Subquery(ratings_avg), 0.0),
            review_count=Coalesce(Subquery(ratings_count), 0),
            total_views=Coalesce(Subquery(views_count), 0)
        ).order_by('-updated_at', '-id')
        store_id = self.request.query_params.get('store')
        if store_id:
            queryset = queryset.filter(store_id=store_id)
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard_summary(request):
    total_stores = Store.objects.count()
    active_stores = Store.objects.filter(status='Open').count()
    total_products = Product.objects.count()
    low_stock = Product.objects.filter(stock__lte=20).count()

    recent_products = Product.objects.select_related('store').order_by('-updated_at', '-id')[:6]
    recent_payload = [
        {
            "id": product.id,
            "store": product.store.name if product.store else "Unassigned",
            "product": product.name,
            "stock": product.stock,
            "status": "Low stock" if product.stock <= 20 else "Healthy",
            "updated_at": product.updated_at,
        }
        for product in recent_products
    ]

    return Response({
        "stats": {
            "total_stores": total_stores,
            "active_stores": active_stores,
            "inventory_items": total_products,
            "low_stock_items": low_stock,
        },
        "recent_activity": recent_payload,
    })

class ProductDetailAPIView(generics.RetrieveAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = []

class ProductRatingView(APIView):
    permission_classes = []

    def get(self, request, product_id):
        from ..services.products.models import ProductRating
        ratings = ProductRating.objects.filter(
            product_id=product_id
        ).select_related('user').order_by('-created_at')

        data = [{
            'id': r.id,
            'user_name': r.user.get_full_name() or r.user.username or r.user.email,
            'rating': r.rating,
            'comment': getattr(r, 'comment', '') or getattr(r, 'review', '') or '',
            'created_at': r.created_at.isoformat(),
        } for r in ratings]
        return Response(data)

    def post(self, request, product_id):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required'}, status=401)
        from ..services.products.models import ProductRating, Product
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=404)

        rating_val = request.data.get('rating', 5)
        comment_val = request.data.get('comment', '') or request.data.get('review', '')

        rating, created = ProductRating.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={
                'rating': rating_val,
                'review': comment_val,
            }
        )
        return Response({'message': 'Rating saved', 'created': created}, status=201)

class StoreRatingView(APIView):
    permission_classes = []

    def post(self, request, store_id):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required'}, status=401)
        from ..services.products.models import Store, StoreRating
        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            return Response({'error': 'Store not found'}, status=404)

        rating, created = StoreRating.objects.update_or_create(
            store=store,
            user=request.user,
            defaults={
                'rating': request.data.get('rating', 5),
                'review': request.data.get('review', ''),
            }
        )
        return Response({'message': 'Rating saved'}, status=201)

    def get(self, request, store_id):
        from ..services.products.models import StoreRating
        ratings = StoreRating.objects.filter(
            store_id=store_id
        ).select_related('user').order_by('-created_at')
        data = [{
            'user_name': r.user.get_full_name() or r.user.username or r.user.email,
            'rating': r.rating,
            'review': getattr(r, 'review', '') or '',
            'created_at': r.created_at.isoformat(),
        } for r in ratings]
        return Response(data)

class BuyerLoginView(APIView):
    permission_classes = []
    def post(self, request):
        from django.contrib.auth import authenticate
        from django.contrib.auth.models import User
        from rest_framework.authtoken.models import Token

        # ── Input sanitization ──
        email = (request.data.get('email') or '').strip().lower()
        password = (request.data.get('password') or '').strip()

        if not email or not password:
            return Response({'error': 'Email and password are required'}, status=400)

        # ── Rate limiting ──
        ip = _get_client_ip(request)
        cache_key = f'login_attempts_buyer_{ip}'
        if _is_rate_limited(cache_key):
            return Response(
                {'error': 'Too many failed login attempts. Please try again in 15 minutes.'},
                status=429
            )

        try:
            user = User.objects.get(email=email)
            auth_user = authenticate(username=user.username, password=password)
        except User.DoesNotExist:
            _record_failed_attempt(cache_key)
            return Response({'error': 'Invalid email or password'}, status=400)

        if not auth_user:
            _record_failed_attempt(cache_key)
            return Response({'error': 'Invalid email or password'}, status=400)

        is_seller = hasattr(auth_user, 'seller')

        if is_seller:
            _record_failed_attempt(cache_key)
            return Response({
                'error': 'This account is a seller account. Please login from the Become a Seller page.'
            }, status=403)

        # Successful login — clear any accumulated failed attempts
        _clear_rate_limit(cache_key)

        token, _ = Token.objects.get_or_create(user=auth_user)
        return Response({
            'token': token.key,
            'user_type': 'buyer',
            'name': auth_user.first_name or auth_user.username or auth_user.email.split('@')[0]
        })

class SellerLoginView(APIView):
    permission_classes = []
    def post(self, request):
        # ── Input sanitization ──
        email = (request.data.get('email') or '').strip().lower()
        password = (request.data.get('password') or '').strip()

        if not email or not password:
            return Response({'error': 'Email and password are required'}, status=400)

        # ── Rate limiting ──
        ip = _get_client_ip(request)
        cache_key = f'login_attempts_seller_{ip}'
        if _is_rate_limited(cache_key):
            return Response(
                {'error': 'Too many failed login attempts. Please try again in 15 minutes.'},
                status=429
            )

        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(username=user_obj.username, password=password)
        except User.DoesNotExist:
            _record_failed_attempt(cache_key)
            return Response({'error': 'Invalid email or password'}, status=400)

        if not user:
            _record_failed_attempt(cache_key)
            return Response({'error': 'Invalid email or password'}, status=400)

        if not hasattr(user, 'seller'):
            _record_failed_attempt(cache_key)
            return Response({'error': 'No seller account found. Please register as a seller first.'}, status=403)

        # Successful login — clear any accumulated failed attempts
        _clear_rate_limit(cache_key)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_type': 'seller',
            'store_name': user.seller.store_name
        })

class TrackStoreViewAPI(APIView):
    permission_classes = []
    def post(self, request):
        store_id = request.data.get('store_id')
        session_id = request.data.get('session_id', '')
        if not store_id:
            return Response({'error': 'store_id required'}, status=400)
        try:
            store = Store.objects.get(id=store_id)
            today = date.today()
            hour = datetime.now().hour
            from ..services.products.models import StoreAnalytics
            analytics, created = StoreAnalytics.objects.get_or_create(
                store=store, date=today, hour=hour,
                defaults={'visitors': 0}
            )
            if not created:
                StoreAnalytics.objects.filter(
                    store=store, date=today, hour=hour
                ).update(visitors=models.F('visitors') + 1)
            else:
                analytics.visitors = 1
                analytics.save()
            return Response({'tracked': True})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class TrackProductViewAPI(APIView):
    permission_classes = []
    def post(self, request):
        product_id = request.data.get('product_id')
        session_id = request.data.get('session_id', '')
        if not product_id:
            return Response({'error': 'product_id required'}, status=400)
        try:
            product = Product.objects.get(id=product_id)
            from ..services.products.models import ProductView
            ProductView.objects.create(
                product=product,
                session_id=session_id,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return Response({'tracked': True})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class CustomPasswordResetView(APIView):
    permission_classes = []

    def post(self, request):
        # ── Input sanitization ──
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'email': ['This field is required.']}, status=400)
        
        from django.contrib.auth.models import User
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.conf import settings
        from urllib.parse import urlparse
        import logging

        logger = logging.getLogger(__name__)

        # Works for both buyers and sellers (any user with that email)
        users = User.objects.filter(email__iexact=email)
        
        for user in users:
            if 'allauth' in settings.INSTALLED_APPS:
                from allauth.account.utils import user_pk_to_url_str
                from allauth.account.forms import default_token_generator
                uid = user_pk_to_url_str(user)
                token = default_token_generator.make_token(user)
            else:
                from django.utils.http import urlsafe_base64_encode
                from django.utils.encoding import force_bytes
                from django.contrib.auth.tokens import default_token_generator
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3002')
            parsed_url = urlparse(frontend_url)
            protocol = parsed_url.scheme
            domain = parsed_url.netloc
            
            context = {
                'username': user.username,
                'uid': uid,
                'token': token,
                'protocol': protocol,
                'domain': domain,
            }
            
            try:
                html_content = render_to_string('registration/password_reset_email.html', context)
                text_content = strip_tags(html_content)
                subject = "Reset Your Gro.Nav Password"
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Gro.Nav <noreply@gronav.com>')
                
                msg = EmailMultiAlternatives(subject, text_content, from_email, [user.email])
                msg.attach_alternative(html_content, "text/html")
                msg.send()
            except Exception as e:
                # Wraps in try/except, logs error if email fails but still returns 200
                logger.error(f"Failed to send password reset email to {user.email}: {e}", exc_info=True)
                
        return Response({'detail': 'Password reset e-mail has been sent.'}, status=200)