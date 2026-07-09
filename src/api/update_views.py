import re

file_path = r"d:\fyp copy2\product_navigator_and_locator-main - Copy\Backend\src\api\seller_dashboard_views.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. get_seller_store
old_get_seller_store = """def get_seller_store(user):
    try:
        seller = user.seller
    except Exception:
        return None

    # Try direct relation:
    try:
        if hasattr(seller, 'store') and seller.store:
            return seller.store
    except:
        pass

    # Try to find Store directly linked to seller:
    from src.services.products.models import Store
    store = Store.objects.filter(
        sellerstore__seller=seller
    ).first()
    if store:
        return store

    # Last resort — find by store name:
    store = Store.objects.filter(
        name=seller.store_name
    ).first()
    return store"""

new_get_seller_store = """def get_seller_store(user):
    \"\"\"Returns the PUBLIC Store object linked to this seller.\"\"\"
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
        return None"""
content = content.replace(old_get_seller_store, new_get_seller_store)

# 2. SellerLoginAPIView return response
old_login_resp = """        return Response({
            "token": token.key,
            "user": {
                "email": user.email,
                "full_name": user.get_full_name(),
                "store_name": seller.seller_store.name if hasattr(seller, 'seller_store') else ""
            }
        })"""
new_login_resp = """        return Response({
            "token": token.key,
            "store_name": seller.store_name,
            "user_type": "seller"
        })"""
content = content.replace(old_login_resp, new_login_resp)

def fix_view_try_block(view_name, old_try_block, new_try_block):
    global content
    if old_try_block in content:
        content = content.replace(old_try_block, new_try_block)
    else:
        print(f"Warning: could not find old block for {view_name}")

# Replace analytics get_seller_and_store with get_seller_store
# Also replace store__name=seller_store.name with store=store
import re

analytics_classes = [
    "SellerAnalyticsVisitorsAPIView",
    "SellerAnalyticsPeakHoursAPIView",
    "SellerAnalyticsHeatmapAPIView",
    "SellerAnalyticsJourneyAPIView",
    "SellerAnalyticsBestTimesAPIView",
    "SellerAnalyticsCompetitorPricesAPIView",
    "SellerAnalyticsRatingsBreakdownAPIView",
    "SellerAnalyticsTopProductsAPIView"
]

for cls in analytics_classes:
    # Use regex to find the class definition and its content up to the next class or EOF
    pattern = r"(class " + cls + r"\(APIView\):.*?)(?=\nclass |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        block = match.group(1)
        # Replace the try block
        old_try = "        try:\n            seller, seller_store = get_seller_and_store(request)\n        except Exception:\n            return Response([], status=200)"
        new_try = "        try:\n            store = get_seller_store(request.user)\n            if not store: return Response([], status=200)\n        except Exception:\n            return Response([], status=200)"
        block = block.replace(old_try, new_try)
        
        # Replace store__name=seller_store.name
        block = block.replace("store__name=seller_store.name", "store=store")
        block = block.replace("product__store__name=seller_store.name", "product__store=store")
        
        content = content[:match.start()] + block + content[match.end():]

# Fix SellerStoreToggleAPIView
old_toggle = """        try:
            seller = request.user.seller
            store = getattr(seller, 'store', None)"""
new_toggle = """        try:
            store = get_seller_store(request.user)"""
content = content.replace(old_toggle, new_toggle)

# Fix SellerDeliveryRadiusAPIView
old_dr_get = """    def get(self, request):
        try:
            seller, seller_store = get_seller_and_store(request)
            store = Store.objects.get(name=seller_store.name)
            dr = DeliveryRadius.objects.get(store=store)
            return Response({'center_lat': dr.center_lat, 'center_lng': dr.center_lng, 'radius_km': dr.radius_km, 'polygon_coords': dr.polygon_coords})
        except Exception:
            return Response({'center_lat': 33.6844, 'center_lng': 73.0479, 'radius_km': 5.0, 'polygon_coords': None})"""
new_dr_get = """    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store: return Response({'center_lat': 33.6844, 'center_lng': 73.0479, 'radius_km': 5.0, 'polygon_coords': None})
            dr = DeliveryRadius.objects.get(store=store)
            return Response({'center_lat': dr.center_lat, 'center_lng': dr.center_lng, 'radius_km': dr.radius_km, 'polygon_coords': dr.polygon_coords})
        except Exception:
            return Response({'center_lat': 33.6844, 'center_lng': 73.0479, 'radius_km': 5.0, 'polygon_coords': None})"""
content = content.replace(old_dr_get, new_dr_get)

old_dr_post = """    def post(self, request):
        try:
            seller, seller_store = get_seller_and_store(request)
            store, _ = Store.objects.get_or_create(name=seller_store.name, defaults={'address': seller_store.address or '', 'phone': seller_store.phone})
            dr, _ = DeliveryRadius.objects.get_or_create(store=store)"""
new_dr_post = """    def post(self, request):
        try:
            store = get_seller_store(request.user)
            if not store: return Response({'error': 'Store not found'}, status=404)
            dr, _ = DeliveryRadius.objects.get_or_create(store=store)"""
content = content.replace(old_dr_post, new_dr_post)

# Fix SellerProductsAPIView.post
old_prod_post = """    def post(self, request):
        print("=== DATA RECEIVED ===")
        print(request.data)
        print("=== FILES ===")
        print(request.FILES)

        try:
            seller, seller_store = get_seller_and_store(request)
        except Exception as e:
            print("STORE ERROR:", e)
            return Response({"error": "Store not found for this seller"}, status=404)

        try:
            # More resilient store lookup (checks both name and unique phone)
            store_name = seller_store.name.strip()
            store = Store.objects.filter(Q(name__iexact=store_name) | Q(phone=seller_store.phone)).first()
            if not store:
                store = Store.objects.create(
                    name=seller_store.name, 
                    address=seller_store.address or '', 
                    phone=seller_store.phone, 
                    city=seller_store.city
                )
            
            data = request.data.copy()
            # Remove store from data if it's there, as it's read-only
            if 'store' in data:
                del data['store']

            # Handle category
            cat_name = data.get('category')
            if cat_name and not str(cat_name).isdigit():
                seller_cat = SellerCategory.objects.filter(store=seller_store, name__iexact=cat_name.strip()).first()
                cat = Category.objects.filter(name__iexact=cat_name.strip()).first()
                if not cat:
                    cat = Category.objects.create(name=cat_name.strip())
                if seller_cat and seller_cat.image and not cat.image:
                    cat.image = seller_cat.image
                    cat.save()
                data['category'] = cat.id

            serializer = ProductSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                # Explicitly pass the store object to save()
                serializer.save(store=store)
                return Response(serializer.data, status=201)
            
            print("=== VALIDATION ERRORS ===")
            print(serializer.errors)
            return Response(serializer.errors, status=400)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return Response({"detail": f"Backend Error: {str(e)}"}, status=500)"""

new_prod_post = """    def post(self, request):
        try:
            seller = request.user.seller
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=404)

        data = request.data.copy()
        data.pop('store', None)

        # Handle category by name:
        cat_name = data.get('category', '')
        if cat_name and not str(cat_name).isdigit():
            cat, _ = Category.objects.get_or_create(name=cat_name.strip())
            data['category'] = cat.id

        serializer = ProductSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save(store=store)
            return Response(serializer.data, status=201)
        print("PRODUCT ERRORS:", serializer.errors)
        return Response(serializer.errors, status=400)"""

content = content.replace(old_prod_post, new_prod_post)

# Fix SellerProductDetailAPIView get_object
old_get_obj = """    def get_object(self, product_id, request):
        try:
            _, seller_store = get_seller_and_store(request)
            # Resilient lookup by name OR phone
            store = Store.objects.filter(
                Q(name__iexact=seller_store.name.strip()) | Q(phone=seller_store.phone)
            ).first()
            if not store:
                return None
            return Product.objects.get(id=product_id, store=store)
        except Product.DoesNotExist:
            return None
        except Exception as e:
            print("get_object ERROR:", e)
            return None"""
new_get_obj = """    def get_object(self, product_id, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return None
            return Product.objects.get(id=product_id, store=store)
        except Product.DoesNotExist:
            return None
        except Exception as e:
            print("get_object error:", e)
            return None"""
content = content.replace(old_get_obj, new_get_obj)

# Fix SellerProductDetailAPIView.put category logic
old_put_cat = """                    _, seller_store = get_seller_and_store(request)
                    seller_cat = SellerCategory.objects.filter(store=seller_store, name__iexact=cat_name.strip()).first()"""
new_put_cat = """                    try:
                        seller_store = request.user.seller.seller_store
                        seller_cat = SellerCategory.objects.filter(store=seller_store, name__iexact=cat_name.strip()).first()
                    except:
                        seller_cat = None"""
content = content.replace(old_put_cat, new_put_cat)

# Fix SellerProductBulkConfirmAPIView
old_bulk_conf = """    def post(self, request):
        try:
            seller, seller_store = get_seller_and_store(request)
        except Exception:
            return Response({"error": "Store not found"}, status=404)
        store, _ = Store.objects.get_or_create(name=seller_store.name, defaults={'address': seller_store.address or '', 'phone': seller_store.phone})"""
new_bulk_conf = """    def post(self, request):
        try:
            store = get_seller_store(request.user)
            if not store:
                return Response({"error": "Store not found"}, status=404)
        except Exception:
            return Response({"error": "Store not found"}, status=404)"""
content = content.replace(old_bulk_conf, new_bulk_conf)

# Fix SellerOrderDetailAPIView
old_order_det = """    def get(self, request, pk):
        try:
            seller, seller_store = get_seller_and_store(request)
        except Exception:
            return Response({"error": "Store not found"}, status=404)
        try:
            order = Order.objects.get(pk=pk, store__name=seller_store.name)"""
new_order_det = """    def get(self, request, pk):
        try:
            store = get_seller_store(request.user)
            if not store: return Response({"error": "Store not found"}, status=404)
        except Exception:
            return Response({"error": "Store not found"}, status=404)
        try:
            order = Order.objects.get(pk=pk, store=store)"""
content = content.replace(old_order_det, new_order_det)

# Fix SellerOrderStatusAPIView
old_order_status = """    def post(self, request, pk):
        try:
            seller, seller_store = get_seller_and_store(request)
        except Exception:
            return Response({"error": "Store not found"}, status=404)
        try:
            order = Order.objects.get(pk=pk, store__name=seller_store.name)"""
new_order_status = """    def post(self, request, pk):
        try:
            store = get_seller_store(request.user)
            if not store: return Response({"error": "Store not found"}, status=404)
        except Exception:
            return Response({"error": "Store not found"}, status=404)
        try:
            order = Order.objects.get(pk=pk, store=store)"""
content = content.replace(old_order_status, new_order_status)

# Fix SellerReturnsAPIView
old_ret = """    def get(self, request):
        try:
            seller, seller_store = get_seller_and_store(request)
        except Exception:
            return Response([], status=200)
        returns = ReturnRequest.objects.filter(order__store__name=seller_store.name).order_by('-created_at')"""
new_ret = """    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store: return Response([], status=200)
        except Exception:
            return Response([], status=200)
        returns = ReturnRequest.objects.filter(order__store=store).order_by('-created_at')"""
content = content.replace(old_ret, new_ret)

# Fix SellerReturnActionAPIView
old_ret_action = """    def post(self, request, pk):
        try:
            seller, seller_store = get_seller_and_store(request)
        except Exception:
            return Response({"error": "Store not found"}, status=404)
        try:
            ret = ReturnRequest.objects.get(pk=pk, order__store__name=seller_store.name)"""
new_ret_action = """    def post(self, request, pk):
        try:
            store = get_seller_store(request.user)
            if not store: return Response({"error": "Store not found"}, status=404)
        except Exception:
            return Response({"error": "Store not found"}, status=404)
        try:
            ret = ReturnRequest.objects.get(pk=pk, order__store=store)"""
content = content.replace(old_ret_action, new_ret_action)

# Fix SellerStoreRatingsAPIView
old_store_rating = """    def get(self, request):
        try:
            from ..services.products.models import StoreRating
            store = get_seller_store(request.user)
            if not store:
                return Response([])
            store = ss.store
            ratings = StoreRating.objects.filter(
                store=store
            ).select_related('user').order_by('-created_at')

            data = [{
                'id': r.id,
                'user_name': r.user.get_full_name() or r.user.username or r.user.email,
                'rating': r.rating,
                'review': getattr(r, 'review', '') or '',
                'created_at': r.created_at.isoformat(),
            } for r in ratings]
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=400)"""

new_store_rating = """    def get(self, request):
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
                'review': getattr(r, 'review', '') or '',
                'created_at': r.created_at.isoformat(),
            } for r in ratings]
            return Response(data)
        except Exception as e:
            return Response({'error': str(e)}, status=400)"""
content = content.replace(old_store_rating, new_store_rating)

# Fix SellerProductRatingsAPIView
old_prod_rating = """    def get(self, request):
        try:
            seller, seller_store = get_seller_and_store(request)
        except Exception:
            return Response([], status=200)
        ratings = ProductRating.objects.filter(product__store__name=seller_store.name).select_related('user', 'product')"""
new_prod_rating = """    def get(self, request):
        try:
            store = get_seller_store(request.user)
            if not store: return Response([], status=200)
        except Exception:
            return Response([], status=200)
        ratings = ProductRating.objects.filter(product__store=store).select_related('user', 'product')"""
content = content.replace(old_prod_rating, new_prod_rating)

# Fix SellerCategoryListCreateAPIView _get_store
old_cat_store = """    def _get_store(self, request):
        try:
            seller = request.user.seller
            return get_seller_store(request.user)
        except Exception:
            return None"""
new_cat_store = """    def _get_store(self, request):
        try:
            seller = request.user.seller
            return seller.seller_store
        except Exception:
            return None"""
content = content.replace(old_cat_store, new_cat_store)

# Fix SellerCategoryDetailAPIView _get_cat
old_cat_det = """    def _get_cat(self, request, pk):
        try:
            _, seller_store = get_seller_and_store(request)
            return SellerCategory.objects.get(pk=pk, store=seller_store)
        except Exception:
            return None"""
new_cat_det = """    def _get_cat(self, request, pk):
        try:
            seller = request.user.seller
            seller_store = seller.seller_store
            return SellerCategory.objects.get(pk=pk, store=seller_store)
        except Exception:
            return None"""
content = content.replace(old_cat_det, new_cat_det)

# Fix BulkImportView
old_bulk_imp = """    def post(self, request):
        try:
            seller = request.user.seller
            from src.services.products.models import Product
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)"""
new_bulk_imp = """    def post(self, request):
        try:
            seller = request.user.seller
            store = get_seller_store(request.user)
            if not store:
                return Response({'error': 'No store found'}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=400)"""
content = content.replace(old_bulk_imp, new_bulk_imp)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
