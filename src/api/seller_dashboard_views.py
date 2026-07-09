from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from django.contrib.auth import authenticate, get_user_model
from rest_framework.authtoken.models import Token
from django.db.models import Avg, Sum, Count, Min, Max, Q, F
from django.db import models
from django.db.models.functions import TruncDate, ExtractHour, ExtractWeekDay
from django.utils import timezone
from datetime import timedelta, date
import json

from ..services.products.models import (
    Store, Product, Order, StoreAnalytics, SellerVerification,
    ProductView, CustomerJourney, HeatmapEvent, StoreRating,
    ProductRating, ReturnRequest, DeliveryRadius, CompetitorPrice, Category
)
from ..services.products.seller_models import Seller, SellerStore, SellerCategory, SellerNotification


def get_time_ago(dt):
    from django.utils import timezone
    now = timezone.now()
    diff = now - dt
    if diff.days > 0:
        if diff.days == 1:
            return 'Yesterday'
        return f"{diff.days} days ago"
    if diff.seconds < 60:
        return 'Just now'
    if diff.seconds < 3600:
        return f"{diff.seconds // 60} minutes ago"
    return f"{diff.seconds // 3600} hours ago"


def create_notification(seller, type, title, message):
    """Helper function — call this whenever notification needed."""
    try:
        SellerNotification.objects.create(
            seller=seller,
            type=type,
            title=title,
            message=message
        )
    except Exception as e:
        print(f"Error creating notification: {e}")
from .serializers import OrderSerializer, SellerVerificationSerializer, ProductSerializer, StoreSerializer



def get_seller_store(user):
    """Returns the PUBLIC Store object linked to this seller."""
    try:
        seller = user.seller
        # Direct OneToOne relation — most reliable:
        store = getattr(seller, 'store', None)
        if store:
            return store
        # Fallback by name:
        from ..services.products.models import Store
        store = Store.objects.filter(seller=seller).first()
        if store:
            return store
        # Last resort — create public store from seller_store data:
        seller_store = getattr(seller, 'seller_store', None)
        if seller_store:
            store, _ = Store.objects.get_or_create(
                seller=seller,
                defaults={
                    'name': seller_store.name,
                    'phone': seller_store.phone,
                    'city': seller_store.city,
                    'address': seller_store.address or '',
                }
            )
            return store
        return None
    except Exception as e:
        print("get_seller_store error:", e)
        return None


def get_seller_and_store(request):
    """Helper: returns (seller, seller_store) or raises exception."""
    try:
        seller = request.user.seller
        # Get or create the internal seller_store
        seller_store = getattr(seller, 'seller_store', None)
        if not seller_store:
            seller_store = SellerStore.objects.create(
                seller=seller,
                name=seller.store_name or 'My Store',
                city=seller.city or '',
                phone=seller.phone or ''
            )
        return seller, seller_store
    except Exception as e:
        print(f"Error in get_seller_and_store: {e}")
        raise e


def get_public_store(seller):
    """Robustly find or create the public Store record for a seller."""
    from ..services.products.models import Store as PublicStore
    
    # 1. Try direct OneToOne link
    store = getattr(seller, 'store', None)
    if store:
        return store
        
    # 2. Try lookup by seller object (redundant but safe)
    store = PublicStore.objects.filter(seller=seller).first()
    if store:
        return store
        
    # 3. Try lookup by phone (unique field)
    if hasattr(seller, 'phone') and seller.phone:
        store = PublicStore.objects.filter(phone=seller.phone).first()
        if store:
            # Link it if it's currently unlinked
            if not store.seller:
                store.seller = seller
                store.save()
            return store

    # 4. Try lookup by name (unique field)
    if hasattr(seller, 'store_name') and seller.store_name:
        store = PublicStore.objects.filter(name=seller.store_name).first()
        if store:
            if not store.seller:
                store.seller = seller
                store.save()
            return store

    # 5. Finally, create a new one if none found
    # Use get_or_create to handle potential race conditions
    store, created = PublicStore.objects.get_or_create(
        seller=seller,
        defaults={
            'name': seller.store_name or f"Store_{seller.id}",
            'phone': seller.phone or f"0000-{seller.id}",
            'city': seller.city or '',
            'address': getattr(seller, 'address', '') or ''
        }
    )
    return store


class SellerOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            try:
                seller = request.user.seller
            except Exception:
                return Response({'error': 'No seller account'}, status=403)

            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=403)

            print("=== OVERVIEW DEBUG ===")
            print("Store:", store.id, store.name)

            from datetime import date
            from django.db.models import Subquery, OuterRef, Count, Avg, Sum
            from django.db.models.functions import Coalesce
            from ..services.products.models import Product, Store, StoreAnalytics, StoreRating, ProductView
            from ..api.models import CustomerOrder

            product_count_sub = Product.objects.filter(store=OuterRef('pk')).values('store').annotate(c=Count('pk')).values('c')
            visitors_sub = StoreAnalytics.objects.filter(store=OuterRef('pk'), date=date.today()).values('store').annotate(s=Sum('visitors')).values('s')
            ratings_sub = StoreRating.objects.filter(store=OuterRef('pk')).values('store').annotate(a=Avg('rating')).values('a')
            review_count_sub = StoreRating.objects.filter(store=OuterRef('pk')).values('store').annotate(c=Count('pk')).values('c')
            views_sub = ProductView.objects.filter(product__store=OuterRef('pk'), viewed_at__date=date.today()).values('product__store').annotate(c=Count('pk')).values('c')
            pending_sub = CustomerOrder.objects.filter(seller=OuterRef('seller__user'), order_status='received').values('seller').annotate(c=Count('pk')).values('c')

            store_data = Store.objects.filter(id=store.id).only(
                'id', 'logo', 'is_open', 'name', 'on_time_delivery_score'
            ).annotate(
                total_products_annotated=Coalesce(Subquery(product_count_sub), 0),
                today_visitors_annotated=Coalesce(Subquery(visitors_sub), 0),
                avg_rating_annotated=Coalesce(Subquery(ratings_sub), 0.0),
                review_count_annotated=Coalesce(Subquery(review_count_sub), 0),
                product_views_today_annotated=Coalesce(Subquery(views_sub), 0),
                pending_orders_annotated=Coalesce(Subquery(pending_sub), 0)
            ).first()

            total_products = store_data.total_products_annotated
            today_visitors = store_data.today_visitors_annotated
            avg_rating = round(float(store_data.avg_rating_annotated), 1)
            review_count = store_data.review_count_annotated
            product_views_today = store_data.product_views_today_annotated
            pending_orders = store_data.pending_orders_annotated
            on_time_score = getattr(store_data, 'on_time_delivery_score', 0)

            # Completion score:
            completion = 0
            if store_data.logo:
                completion += 10
            if total_products >= 5:
                completion += 20
            try:
                if seller.sellerverification.is_verified:
                    completion += 30
            except:
                pass
            if hasattr(store_data, 'deliveryradius'):
                completion += 20
            if review_count >= 5:
                completion += 20

            return Response({
                'total_products': total_products,
                'today_visitors': today_visitors,
                'product_views_today': product_views_today,
                'avg_rating': avg_rating,
                'review_count': review_count,
                'pending_orders': pending_orders,
                'on_time_score': on_time_score,
                'completion_score': completion,
                'store_status': 'Active' if store_data.is_open else 'Closed',
                'is_open': store_data.is_open,
                'store_name': store_data.name,
                'store_logo': request.build_absolute_uri(store_data.logo.url) if store_data.logo else None,
            })

        except Exception as e:
            print("OVERVIEW ERROR:", e)
            import traceback
            traceback.print_exc()
            return Response({'error': str(e)}, status=400)


class SellerLoginAPIView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({"error": "Email and password are required"}, status=400)

        User = get_user_model()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid email or password"}, status=400)

        if not user.check_password(password):
            return Response({"error": "Invalid email or password"}, status=400)

        try:
            seller = user.seller
        except Exception:
            return Response({"error": "This account is not registered as a seller"}, status=403)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({
            "token": token.key,
            "store_name": seller.store_name,
            "user_type": "seller"
        })


class SellerAnalyticsVisitorsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return Response([], status=200)
        except Exception:
            return Response([], status=200)

        since = timezone.now().date() - timedelta(days=30)
        analytics = StoreAnalytics.objects.filter(
            store=store, date__gte=since
        ).values('date').annotate(visitors=Sum('visitors')).order_by('date')

        views = ProductView.objects.filter(
            product__store=store,
            viewed_at__date__gte=since
        ).values('viewed_at__date').annotate(product_views=Count('id')).order_by('viewed_at__date')

        views_map = {str(v['viewed_at__date']): v['product_views'] for v in views}
        result = []
        for a in analytics:
            result.append({
                'date': str(a['date']),
                'visitors': a['visitors'],
                'product_views': views_map.get(str(a['date']), 0)
            })
        return Response(result)


class SellerAnalyticsPeakHoursAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return Response([], status=200)
        except Exception:
            return Response([], status=200)

        since = timezone.now() - timedelta(days=90)
        data = StoreAnalytics.objects.filter(
            store=store, date__gte=since.date()
        ).values('hour').annotate(count=Sum('visitors')).order_by('hour')
        return Response(list(data))


class SellerAnalyticsHeatmapAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return Response([])
        except Exception:
            return Response([])

        data = HeatmapEvent.objects.filter(
            store=store
        ).values('section').annotate(
            avg_scroll_depth=Avg('scroll_depth'),
            view_count=Count('id')
        ).order_by('-view_count')

        return Response(list(data))



class SellerAnalyticsJourneyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return Response([])
        except Exception:
            return Response([])

        steps = ['view', 'cart', 'checkout']
        result = []
        prev_count = None
        for step in steps:
            count = CustomerJourney.objects.filter(
                store=store,
                action=step
            ).count()
            if prev_count and prev_count > 0:
                conv = round((count / prev_count * 100), 1)
            else:
                conv = 100.0 if step == 'view' else 0.0
            result.append({
                'step': step.capitalize(),
                'count': count,
                'conversion_rate': conv
            })
            prev_count = count
        return Response(result)



class SellerAnalyticsBestTimesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return Response({'grid': [], 'prediction': []})
        except Exception:
            return Response({'grid': [], 'prediction': []})

        since = timezone.now().date() - timedelta(days=90)

        data = StoreAnalytics.objects.filter(
            store=store,
            date__gte=since
        ).annotate(
            day_of_week=ExtractWeekDay('date')
        ).values('day_of_week', 'hour').annotate(
            traffic_score=Sum('visitors')
        ).order_by('day_of_week', 'hour')

        top_times = StoreAnalytics.objects.filter(
            store=store,
            date__gte=since
        ).annotate(
            day_of_week=ExtractWeekDay('date')
        ).values('day_of_week', 'hour').annotate(
            total=Sum('visitors')
        ).order_by('-total')[:5]

        days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
        prediction = []
        for t in top_times:
            if t['day_of_week']:
                day_name = days[t['day_of_week'] - 1]
                hour = t['hour']
                am_pm = 'AM' if hour < 12 else 'PM'
                hour_12 = hour if hour <= 12 else hour - 12
                hour_12 = 12 if hour_12 == 0 else hour_12
                prediction.append(f"{day_name} {hour_12}{am_pm}")

        return Response({
            'grid': list(data),
            'prediction': prediction[:3]
        })



class SellerAnalyticsCompetitorPricesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return Response([])
        except Exception as e:
            print("Competitor error getting store:", e)
            return Response([])

        print("=== COMPETITOR DEBUG ===")
        print("My store:", store.id, store.name)

        # Get all categories this seller has products in:
        my_categories = Category.objects.filter(
            products__store=store
        ).distinct()

        print("My categories:", list(my_categories.values_list('name', flat=True)))

        result = []
        for category in my_categories:
            # My products in this category:
            my_products = Product.objects.filter(
                store=store,
                category=category
            )

            if not my_products.exists():
                continue

            my_avg = my_products.aggregate(
                avg=Avg('price')
            )['avg'] or 0

            print(f"Category: {category.name} | My products: {my_products.count()} | My avg: {my_avg}")

            # Competitor products — same category, different store:
            competitor_products = Product.objects.filter(
                category=category
            ).exclude(
                store=store
            )

            print(f"Competitor products: {competitor_products.count()}")

            if competitor_products.exists():
                market_avg = competitor_products.aggregate(
                    avg=Avg('price')
                )['avg'] or 0
                lowest = competitor_products.aggregate(
                    low=Min('price')
                )['low'] or 0
                competitor_store_count = competitor_products.values('store').distinct().count()
            else:
                market_avg = my_avg
                lowest = my_avg
                competitor_store_count = 0

            my_avg_f = round(float(my_avg), 2)
            market_avg_f = round(float(market_avg), 2)
            lowest_f = round(float(lowest), 2)

            margin = float(market_avg) * 0.05
            my_avg_float = float(my_avg)
            market_avg_float = float(market_avg)
            if my_avg_float > market_avg_float + margin:
                status = 'overpriced'
            elif my_avg_float < market_avg_float - margin:
                status = 'underpriced'
            else:
                status = 'competitive'

            result.append({
                'category': category.name,
                'my_avg_price': my_avg_f,
                'market_avg': market_avg_f,
                'lowest_price': lowest_f,
                'status': status,
                'my_product_count': my_products.count(),
                'competitor_count': competitor_store_count,
            })

        print("Result:", result)

        # Sort: overpriced first:
        result.sort(key=lambda x: 0 if x['status'] == 'overpriced' else 1)
        return Response(result)



class SellerAnalyticsRatingsBreakdownAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store: return Response([], status=200)
        except Exception:
            return Response([], status=200)

        data = StoreRating.objects.filter(
            store=store
        ).values('rating').annotate(count=Count('id')).order_by('-rating')
        return Response([{'stars': d['rating'], 'count': d['count']} for d in data])


class SellerAnalyticsTopProductsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store: return Response([], status=200)
        except Exception:
            return Response([], status=200)

        products = Product.objects.filter(store=store).annotate(
            views=Count('productview'),
            avg_rating=Avg('productrating__rating')
        )[:10]
        result = [{
            'product_name': p.name,
            'views': p.views,
            'avg_rating': round(p.avg_rating or 0, 1),
            'conversion_rate': 0,
        } for p in products]
        return Response(result)


class SellerStoreAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            seller = request.user.seller
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=403)
        except Exception:
            return Response({'error': 'No seller account found'}, status=403)

        serializer = StoreSerializer(store, context={'request': request})
        return Response(serializer.data)

    def put(self, request):
        try:
            seller = request.user.seller
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=403)
        except Exception:
            return Response({'error': 'No seller account found'}, status=403)

        serializer = StoreSerializer(
            store, data=request.data,
            partial=True, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            
            # Sync with SellerStore too
            try:
                seller_store = seller.seller_store
                for field in ['name', 'city', 'address', 'phone', 'opening_hours']:
                    if field in request.data:
                        setattr(seller_store, field, request.data[field])
                if 'logo' in request.FILES:
                    seller_store.logo = request.FILES['logo']
                seller_store.save()
            except:
                pass

            return Response(serializer.data)
        print("ERRORS:", serializer.errors)
        return Response(serializer.errors, status=400)

class SellerStoreToggleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=404)
            store.is_open = not store.is_open
            store.save(update_fields=['is_open'])  # explicitly save only is_open
            print("Store is_open updated to:", store.is_open)
            return Response({'is_open': store.is_open})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class SellerDeliveryRadiusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store: return Response({'center_lat': 33.6844, 'center_lng': 73.0479, 'radius_km': 5.0, 'polygon_coords': None})
            dr = DeliveryRadius.objects.get(store=store)
            return Response({'center_lat': dr.center_lat, 'center_lng': dr.center_lng, 'radius_km': dr.radius_km, 'polygon_coords': dr.polygon_coords})
        except Exception:
            return Response({'center_lat': 33.6844, 'center_lng': 73.0479, 'radius_km': 5.0, 'polygon_coords': None})

    def post(self, request):
        try:
            store = get_seller_store(request.user)
            if not store: return Response({'error': 'Store not found'}, status=404)
            dr, _ = DeliveryRadius.objects.get_or_create(store=store)
            dr.center_lat = request.data.get('center_lat', 33.6844)
            dr.center_lng = request.data.get('center_lng', 73.0479)
            dr.radius_km = request.data.get('radius_km', 5.0)
            dr.polygon_coords = request.data.get('polygon_coords', None)
            dr.save()
            return Response({'message': 'Delivery radius saved'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class SellerProductsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            seller = request.user.seller
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=403)
        except Exception:
            return Response({'error': 'No seller account'}, status=403)

        from django.db.models import Subquery, OuterRef, Count, Avg
        from django.db.models.functions import Coalesce
        from ..services.products.models import ProductRating, ProductView

        ratings_avg = ProductRating.objects.filter(product=OuterRef('pk')).values('product').annotate(avg=Avg('rating')).values('avg')
        ratings_count = ProductRating.objects.filter(product=OuterRef('pk')).values('product').annotate(count=Count('id')).values('count')
        views_count = ProductView.objects.filter(product=OuterRef('pk')).values('product').annotate(count=Count('id')).values('count')

        products = Product.objects.filter(store=store).select_related('category', 'store').annotate(
            avg_rating=Coalesce(Subquery(ratings_avg), 0.0),
            review_count=Coalesce(Subquery(ratings_count), 0),
            total_views=Coalesce(Subquery(views_count), 0)
        )
        
        serializer = ProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)
    
    def post(self, request):
        try:
            seller = request.user.seller
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=404)

        data = request.data.copy()
        data.pop('store', None)

        # When category name comes as string (not ID):
        cat_name = str(data.get('category', '')).strip()
        if cat_name and not str(cat_name).isdigit():
            # Case insensitive get or create:
            try:
                category = Category.objects.get(name__iexact=cat_name)
            except Category.DoesNotExist:
                category = Category.objects.create(name=cat_name)

            # Also add to SellerCategory:
            try:
                seller_store = request.user.seller.seller_store
                SellerCategory.objects.get_or_create(
                    store=seller_store,
                    name=cat_name
                )
            except Exception:
                pass

            data['category'] = category.id

        serializer = ProductSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            product = serializer.save(store=store)

            # Check for low stock alert
            if product.stock <= product.stock_alert_threshold:
                SellerNotification.objects.get_or_create(
                    seller=seller,
                    type='low_stock',
                    title='Low Stock Alert',
                    message=f'"{product.name}" is running low! Only {product.stock} units remaining. (Alert threshold: {product.stock_alert_threshold})',
                    defaults={'is_read': False}
                )

            return Response(serializer.data, status=201)
        print("PRODUCT ERRORS:", serializer.errors)
        return Response(serializer.errors, status=400)


class SellerProductDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, product_id, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return None
            return Product.objects.get(id=product_id, store=store)
        except Product.DoesNotExist:
            return None
        except Exception as e:
            print("get_object error:", e)
            return None

    def get(self, request, product_id):
        product = self.get_object(product_id, request)
        if not product:
            return Response({"error": "Product not found"}, status=404)
        return Response(ProductSerializer(product, context={'request': request}).data)

    def put(self, request, product_id):
        product = self.get_object(product_id, request)
        if not product:
            return Response({'error': 'Product not found'}, status=404)
            
        try:
            data = request.data.copy()
            # Remove store — it's read-only, set by backend
            data.pop('store', None)
            
            # Handle category by name if provided
            if 'category' in data:
                cat_name = data.get('category')
                if cat_name and not str(cat_name).isdigit():
                    try:
                        seller_store = request.user.seller.seller_store
                        seller_cat = SellerCategory.objects.filter(store=seller_store, name__iexact=cat_name.strip()).first()
                    except:
                        seller_cat = None
                    cat = Category.objects.filter(name__iexact=cat_name.strip()).first()
                    if not cat:
                        cat = Category.objects.create(name=cat_name.strip())
                    if seller_cat and seller_cat.image and not cat.image:
                        cat.image = seller_cat.image
                        cat.save()
                    data['category'] = cat.id

            serializer = ProductSerializer(product, data=data, partial=True, context={'request': request})
            if serializer.is_valid():
                updated_product = serializer.save()

                # Check for low stock alert
                if updated_product.stock <= updated_product.stock_alert_threshold:
                    SellerNotification.objects.get_or_create(
                        seller=request.user.seller,
                        type='low_stock',
                        title='Low Stock Alert',
                        message=f'"{updated_product.name}" is running low! Only {updated_product.stock} units remaining. (Alert threshold: {updated_product.stock_alert_threshold})',
                        defaults={'is_read': False}
                    )

                return Response(serializer.data)
            print("UPDATE ERRORS:", serializer.errors)
            return Response(serializer.errors, status=400)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({"detail": str(e)}, status=500)

    def delete(self, request, product_id):
        product = self.get_object(product_id, request)
        if not product:
            return Response({'error': 'Product not found'}, status=404)
        product.delete()
        return Response({'message': 'Product deleted'}, status=204)


class SellerProductBulkConfirmAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            seller = request.user.seller
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

        products_data = request.data.get('rows', [])
        if not products_data:
            products_data = request.data.get('products', [])
        if not products_data:
            return Response({'error': 'No product data provided'}, status=400)

        created = 0
        updated = 0
        errors = []

        for row in products_data:
            try:
                name = str(row.get('name', '')).strip()
                if not name:
                    continue

                # Get or create category — case insensitive:
                cat_name = str(row.get('category', 'General')).strip()
                category, _ = Category.objects.get_or_create(
                    name__iexact=cat_name,
                    defaults={'name': cat_name}
                )

                # Also create in SellerCategory for this seller:
                try:
                    seller_store = seller.seller_store
                    SellerCategory.objects.get_or_create(
                        store=seller_store,
                        name=cat_name
                    )
                except Exception:
                    pass

                # Build product data:
                price = float(row.get('price', 0) or 0)
                stock = int(row.get('stock', 0) or 0)
                description = str(row.get('description', '') or '')
                featured = str(row.get('featured_product', '')).lower() == 'true'

                expiry_date = None
                expiry_raw = row.get('expiry_date', '')
                if expiry_raw:
                    try:
                        from datetime import datetime
                        expiry_date = datetime.strptime(str(expiry_raw), '%Y-%m-%d').date()
                    except:
                        try:
                            expiry_date = datetime.strptime(str(expiry_raw), '%d/%m/%Y').date()
                        except:
                            expiry_date = None

                discount = None
                discount_raw = row.get('discount_percentage', '')
                if discount_raw:
                    try:
                        discount = float(discount_raw)
                    except:
                        discount = None

                # Update if exists in this store, create if not:
                product, was_created = Product.objects.update_or_create(
                    name=name,
                    store=store,
                    defaults={
                        'category': category,
                        'price': price,
                        'stock': stock,
                        'description': description,
                        'featured_product': featured,
                        'expiry_date': expiry_date,
                        'discount_percentage': discount,
                    }
                )

                if was_created:
                    created += 1
                else:
                    updated += 1

            except Exception as e:
                import traceback
                print(traceback.format_exc())
                errors.append(f"{row.get('name', 'unknown')}: {str(e)}")

        return Response({
            'created': created,
            'updated': updated,
            'errors': errors,
            'message': f'{created} products created, {updated} updated successfully'
        })


class SellerOrdersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            seller = request.user.seller
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=403)
        except Exception:
            return Response({'error': 'No seller account'}, status=403)

        orders = Order.objects.filter(store=store).select_related('buyer', 'store').prefetch_related('items', 'items__product').order_by('-created_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)


class SellerOrderDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            store = get_seller_store(request.user)
            if not store: return Response({"error": "Store not found"}, status=404)
        except Exception:
            return Response({"error": "Store not found"}, status=404)
        try:
            order = Order.objects.get(pk=pk, store=store)
            return Response(OrderSerializer(order).data)
        except Order.DoesNotExist:
            return Response({"error": "Not found"}, status=404)


class SellerOrderStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            store = get_seller_store(request.user)
            if not store: return Response({"error": "Store not found"}, status=404)
        except Exception:
            return Response({"error": "Store not found"}, status=404)
        try:
            order = Order.objects.get(pk=pk, store=store)
            new_status = request.data.get('status')
            valid = [s[0] for s in Order.STATUS]
            if new_status not in valid:
                return Response({"error": "Invalid status"}, status=400)
            order.status = new_status
            order.save()

            # Notification for certain status changes
            titles = {
                'processing': 'Order Processing',
                'shipped': 'Order Shipped',
                'delivered': 'Order Delivered',
                'cancelled': 'Order Cancelled'
            }
            if new_status in titles:
                create_notification(
                    seller=store.seller,
                    type='order',
                    title=titles[new_status],
                    message=f"Order #{order.id} status updated to {new_status}."
                )

            return Response({"status": order.status, "message": "Order status updated"})
        except Order.DoesNotExist:
            return Response({"error": "Not found"}, status=404)


class SellerReturnsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store: return Response([], status=200)
        except Exception:
            return Response([], status=200)
        returns = ReturnRequest.objects.filter(order__store=store).order_by('-created_at')
        data = [{'id': r.id, 'order_id': r.order_id, 'reason': r.reason, 'status': r.status, 'created_at': str(r.created_at)} for r in returns]
        return Response(data)


class SellerReturnActionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            store = get_seller_store(request.user)
            if not store: return Response({"error": "Store not found"}, status=404)
        except Exception:
            return Response({"error": "Store not found"}, status=404)
        try:
            ret = ReturnRequest.objects.get(pk=pk, order__store=store)
            action = request.data.get('action')
            if action not in ['approved', 'rejected']:
                return Response({"error": "Invalid action"}, status=400)
            ret.status = action
            ret.save()
            return Response({"status": ret.status})
        except ReturnRequest.DoesNotExist:
            return Response({"error": "Not found"}, status=404)


class SellerVerificationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            seller = request.user.seller
            verification = seller.sellerverification
            return Response({
                'cnic_number': verification.cnic_number,
                'is_verified': verification.is_verified,
                'submitted_at': str(verification.submitted_at),
                'status': 'Verified' if verification.is_verified else 'Pending'
            })
        except Exception:
            return Response({"status": "Not submitted", "is_verified": False})

    def post(self, request):
        try:
            seller = request.user.seller
        except Exception:
            return Response({"error": "Seller not found"}, status=404)
        cnic = request.data.get('cnic_number', '')
        if not cnic:
            return Response({"error": "CNIC number required"}, status=400)
        verification, _ = SellerVerification.objects.get_or_create(seller=seller)
        verification.cnic_number = cnic
        if 'cnic_front' in request.FILES:
            verification.cnic_front = request.FILES['cnic_front']
        if 'cnic_back' in request.FILES:
            verification.cnic_back = request.FILES['cnic_back']
        verification.save()
        return Response({"message": "Verification submitted", "status": "Pending"})


class SellerStoreRatingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return Response([])
            ratings = StoreRating.objects.filter(
                store=store
            ).select_related('user').order_by('-created_at')
            data = [{
                'id': r.id,
                'user_name': r.user.get_full_name() or r.user.username or r.user.email,
                'rating': r.rating,
                'review': r.review or '',
                'created_at': r.created_at.isoformat(),
            } for r in ratings]
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class SellerProductRatingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store: return Response([], status=200)
        except Exception:
            return Response([], status=200)
        ratings = ProductRating.objects.filter(product__store=store).select_related('user', 'product')
        data = [{'product': r.product.name, 'user': r.user.get_full_name() or r.user.username, 'rating': r.rating, 'review': r.review, 'created_at': str(r.created_at)} for r in ratings]
        return Response(data)





class SellerSettingsPasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current = request.data.get('current_password', '')
        new_pass = request.data.get('new_password', '')
        if not user.check_password(current):
            return Response({"error": "Current password is incorrect"}, status=400)
        if len(new_pass) < 8:
            return Response({"error": "Password must be at least 8 characters"}, status=400)
        user.set_password(new_pass)
        user.save()
        return Response({"message": "Password updated successfully"})


class SellerSettingsDeleteAccountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.delete()
        return Response({"message": "Account deleted"}, status=204)





class TrackStoreViewAPIView(APIView):
    permission_classes = []

    def post(self, request):
        store_id = request.data.get('store_id')
        session_id = request.data.get('session_id', '')
        if not store_id:
            return Response({'error': 'store_id required'}, status=400)
        try:
            store = Store.objects.get(pk=store_id)
            today = date.today()
            hour = timezone.now().hour
            analytics, created = StoreAnalytics.objects.get_or_create(
                store=store,
                date=today,
                hour=hour,
                defaults={'visitors': 0}
            )
            StoreAnalytics.objects.filter(
                store=store, date=today, hour=hour
            ).update(visitors=models.F('visitors') + 1)
            return Response({'tracked': True})
        except Store.DoesNotExist:
            return Response({'error': 'Store not found'}, status=404)
        except Exception as e:
            print("Track store error:", e)
            return Response({'error': str(e)}, status=400)


class TrackProductViewAPIView(APIView):
    permission_classes = []

    def post(self, request):
        product_id = request.data.get('product_id')
        session_id = request.data.get('session_id', '')
        if not product_id:
            return Response({'error': 'product_id required'}, status=400)
        try:
            product = Product.objects.get(pk=product_id)
            ProductView.objects.create(
                product=product,
                session_id=session_id,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return Response({'tracked': True})
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=404)
        except Exception as e:
            print("Track product error:", e)
            return Response({'error': str(e)}, status=400)


class TrackJourneyAPIView(APIView):
    permission_classes = []

    def post(self, request):
        step = request.data.get('step', '')
        product_id = request.data.get('product_id')
        store_id = request.data.get('store_id')
        session_id = request.data.get('session_id', '')
        if not step:
            return Response({'error': 'step required'}, status=400)
        try:
            product = Product.objects.get(pk=product_id) if product_id else None
            store = Store.objects.get(pk=store_id) if store_id else None
            if not store and product:
                store = product.store
            if not store:
                return Response({'error': 'store required'}, status=400)
            CustomerJourney.objects.create(
                session_id=session_id,
                product=product,
                store=store,
                action=step.lower()
            )
            return Response({'tracked': True})
        except Exception as e:
            print("Track journey error:", e)
            return Response({'error': str(e)}, status=400)


class TrackHeatmapAPIView(APIView):
    permission_classes = []

    def post(self, request):
        section = request.data.get('section', '')
        depth = request.data.get('depth', 0)
        product_id = request.data.get('product_id')
        store_id = request.data.get('store_id')
        session_id = request.data.get('session_id', '')
        if not section:
            return Response({'error': 'section required'}, status=400)
        try:
            product = Product.objects.get(pk=product_id) if product_id else None
            store = Store.objects.get(pk=store_id) if store_id else None
            if not store and product:
                store = product.store
            HeatmapEvent.objects.create(
                product=product,
                store=store,
                session_id=session_id,
                scroll_depth=int(depth),
                section=section
            )
            return Response({'tracked': True})
        except Exception as e:
            print("Track heatmap error:", e)
            return Response({'error': str(e)}, status=400)



# ─── Seller Category Views ────────────────────────────────────────────────────

class SellerCategoryListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_store(self, request):
        try:
            seller = request.user.seller
            return seller.seller_store
        except Exception:
            return None

    def get(self, request):
        store = self._get_store(request)
        if not store:
            return Response([], status=200)
        categories = SellerCategory.objects.filter(store=store).order_by('name')
        data = []
        for cat in categories:
            image_url = request.build_absolute_uri(cat.image.url) if cat.image else None
            try:
                general_cat = Category.objects.get(name=cat.name)
                count = Product.objects.filter(store__name=store.name, category=general_cat).count()
            except Exception:
                count = 0
            data.append({
                'id': cat.id,
                'name': cat.name,
                'image': cat.image.name if cat.image else None,
                'image_url': image_url,
                'product_count': count,
                'created_at': str(cat.created_at),
            })
        return Response(data)

    def post(self, request):
        store = self._get_store(request)
        if not store:
            return Response({'error': 'Store not found'}, status=400)
        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': 'Category name is required'}, status=400)
        if SellerCategory.objects.filter(store=store, name=name).exists():
            return Response({'error': 'Category with this name already exists'}, status=400)
        cat = SellerCategory(store=store, name=name)
        if 'image' in request.FILES:
            cat.image = request.FILES['image']
        cat.save()
        image_url = request.build_absolute_uri(cat.image.url) if cat.image else None
        return Response({
            'id': cat.id, 'name': cat.name, 'image_url': image_url,
            'product_count': 0, 'created_at': str(cat.created_at)
        }, status=201)


class SellerCategoryDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_cat(self, request, pk):
        try:
            seller = request.user.seller
            seller_store = seller.seller_store
            return SellerCategory.objects.get(pk=pk, store=seller_store)
        except Exception:
            return None

    def put(self, request, pk):
        cat = self._get_cat(request, pk)
        if not cat:
            return Response({'error': 'Not found'}, status=404)
        name = request.data.get('name', '').strip()
        if name:
            if SellerCategory.objects.filter(store=cat.store, name=name).exclude(pk=pk).exists():
                return Response({'error': 'Category with this name already exists'}, status=400)
            cat.name = name
        if 'image' in request.FILES:
            cat.image = request.FILES['image']
        cat.save()
        image_url = request.build_absolute_uri(cat.image.url) if cat.image else None
        try:
            general_cat = Category.objects.get(name=cat.name)
            count = Product.objects.filter(store__name=cat.store.name, category=general_cat).count()
        except Exception:
            count = 0
        return Response({
            'id': cat.id, 'name': cat.name, 'image_url': image_url,
            'product_count': count, 'created_at': str(cat.created_at)
        })

    def delete(self, request, pk):
        cat = self._get_cat(request, pk)
        if not cat:
            return Response({'error': 'Not found'}, status=404)
        cat.delete()
        return Response(status=204)

class ProductStoreDetailAPIView(APIView):
    permission_classes = []  # public endpoint

    def get(self, request, product_id):
        try:
            product = Product.objects.select_related('store').get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=404)
        
        store = product.store
        if not store:
            return Response({'error': 'This product is not linked to any store yet.'}, status=404)
        
        try:
            # Use 'schedule' field (the actual Store model field name from shell output)
            opening_hours = getattr(store, 'schedule', None) or getattr(store, 'opening_hours', '9am - 9pm')
            address = getattr(store, 'address', '')
            city = getattr(store, 'city', '')
            
            data = {
                'store_id': store.id,
                'store_name': store.name,
                'address': address,
                'city': city,
                'phone': getattr(store, 'phone', ''),
                'opening_hours': opening_hours or '9am - 9pm',
                'is_open': getattr(store, 'is_open', None),
                'google_maps_url': f"https://maps.google.com/?q={address}+{city}",
                'logo': request.build_absolute_uri(store.image.url) if store.image else None,
                'seller_type': store.seller.seller_type if store.seller else 'online',
            }

            return Response(data)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({'error': str(e)}, status=400)


class BulkImportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            seller = request.user.seller
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

        rows = request.data.get('rows', [])
        if not rows:
            return Response({'error': 'No data provided'}, status=400)

        created = 0
        updated = 0
        errors = []

        for row in rows:
            try:
                name = row.get('name', '').strip()
                if not name:
                    continue

                # Find category
                category = None
                cat_name = row.get('category', '')
                if cat_name:
                    from src.services.products.models import Category
                    category, _ = Category.objects.get_or_create(name=cat_name)

                product_data = {
                    'store': store,
                    'category': category,
                    'price': row.get('price', 0),
                    'stock': row.get('stock', 0),
                    'description': row.get('description', ''),
                    'featured_product': str(row.get('featured_product', '')).lower() == 'true',
                }

                expiry = row.get('expiry_date', '')
                if expiry:
                    product_data['expiry_date'] = expiry

                discount = row.get('discount_percentage', '')
                if discount:
                    product_data['discount_percentage'] = discount

                # Update if exists, create if not
                product, was_created = Product.objects.update_or_create(
                    name=name,
                    store=store,
                    defaults=product_data
                )

                if was_created:
                    created += 1
                else:
                    updated += 1

            except Exception as e:
                errors.append(f"{row.get('name', 'unknown')}: {str(e)}")

        return Response({
            'created': created,
            'updated': updated,
            'errors': errors
        })


class SellerNotificationsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            seller = request.user.seller
        except Exception:
            return Response({'notifications': [], 'unread_count': 0})

        notifications = SellerNotification.objects.filter(
            seller=seller
        ).order_by('-created_at')[:20]

        data = [{
            'id': n.id,
            'type': n.type,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
            'time_ago': get_time_ago(n.created_at),
        } for n in notifications]

        unread_count = SellerNotification.objects.filter(seller=seller, is_read=False).count()

        return Response({
            'notifications': data,
            'unread_count': unread_count
        })

    def post(self, request):
        # Mark all as read:
        try:
            seller = request.user.seller
            SellerNotification.objects.filter(
                seller=seller,
                is_read=False
            ).update(is_read=True)
            return Response({'message': 'All marked as read'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class SellerNotificationReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            seller = request.user.seller
            notif = SellerNotification.objects.get(pk=pk, seller=seller)
            notif.is_read = True
            notif.save()
            return Response({'message': 'Marked as read'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)
