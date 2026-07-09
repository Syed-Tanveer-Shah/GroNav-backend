from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from src.services.products.models import Product
from .models import CustomerOrder
from .email_service import (
    send_order_confirmation_email,
    send_order_received_by_seller_email,
    send_order_packed_email,
    send_order_out_for_delivery_email,
    send_order_delivered_email,
    send_verification_complete_seller_notification,
)

class CreateOrderView(APIView):
    """
    POST /api/orders/create/
    Body parameters:
    - product_id: ID of the product
    - quantity: Quantity of product ordered
    - customer_name: Full name of customer
    - customer_phone: Phone number of customer
    - delivery_address: Address for delivery
    - payment_method: stripe or COD
    - payment_status: paid or pending
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            data = request.data
            product_id = data.get('product_id')
            quantity = int(data.get('quantity', 1))
            payment_method = data.get('payment_method', 'COD')
            payment_status = data.get('payment_status', 'pending')
            
            customer_name = data.get('customer_name')
            customer_phone = data.get('customer_phone')
            delivery_address = data.get('delivery_address')
            
            if not product_id or not customer_name or not customer_phone or not delivery_address:
                return Response({'error': 'Missing required fields.'}, status=400)
                
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return Response({'error': 'Product not found.'}, status=404)
                
            # Compute prices
            price = product.get_discounted_price() if hasattr(product, 'get_discounted_price') else product.price
            total_amount = (price * quantity) + 140 + 10  # Items + Delivery + Platform
            
            # Find seller
            seller_user = None
            store = product.store
            if store and store.seller:
                seller_user = store.seller.user
                
            # Create order record
            order = CustomerOrder.objects.create(
                customer=request.user,
                seller=seller_user,
                store=store,
                product=product,
                product_name=product.name,
                quantity=quantity,
                price_per_item=price,
                total_amount=total_amount,
                delivery_fee=140.00,
                platform_fee=10.00,
                payment_method=payment_method,
                payment_status=payment_status,
                order_status='received',
                delivery_address=delivery_address,
                customer_name=customer_name,
                customer_phone=customer_phone
            )
            
            # Decrement stock
            if product.stock >= quantity:
                product.stock -= quantity
                product.save()

            if product.stock <= product.stock_alert_threshold:
                try:
                    from .models import SellerNotification
                    seller = product.store.seller
                    if seller:
                        SellerNotification.objects.get_or_create(
                            seller=seller,
                            type='low_stock',
                            title='Low Stock Alert',
                            message=f'"{product.name}" is running low! Only {product.stock} units remaining.',
                            defaults={
                                'is_read': False
                            }
                        )
                except Exception as e:
                    print(f"Stock alert notification error: {e}")

            # ── Trigger order emails asynchronously ──────────────────────────
            from threading import Thread
            from .email_service import send_order_confirmation_email, send_order_received_by_seller_email
            Thread(target=send_order_confirmation_email, args=(order,)).start()
            print(f"Order email triggered for: {order.customer.email}")
            Thread(target=send_order_received_by_seller_email, args=(order,)).start()
            # ─────────────────────────────────────────────────────────────

            return Response({
                'order_id': order.order_id,
                'message': 'Order created successfully.'
            }, status=201)
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class SellerOrderListView(APIView):
    """
    GET /api/orders/seller/
    Query parameters:
    - status: active / all / returns
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            try:
                seller = request.user.seller
            except Exception:
                return Response({'error': 'User is not registered as a seller.'}, status=403)

            status_filter = request.query_params.get('status', 'all')
            
            queryset = CustomerOrder.objects.filter(seller=request.user).order_by('-created_at')
            
            if status_filter == 'active':
                queryset = queryset.exclude(order_status__in=['delivered', 'cancelled'])
            elif status_filter == 'returns':
                queryset = queryset.filter(order_status='cancelled')
            elif status_filter in ('completed', 'delivered'):
                queryset = queryset.filter(order_status='delivered')
                
            data = []
            for order in queryset:
                data.append({
                    'id': order.order_id,
                    'customer_name': order.customer_name,
                    'customer_phone': order.customer_phone,
                    'product_name': order.product_name,
                    'quantity': order.quantity,
                    'price_per_item': float(order.price_per_item),
                    'total_amount': float(order.total_amount),
                    'delivery_fee': float(order.delivery_fee),
                    'platform_fee': float(order.platform_fee),
                    'payment_method': order.payment_method,
                    'payment_status': order.payment_status,
                    'order_status': order.order_status,
                    'delivery_address': order.delivery_address,
                    'created_at': order.created_at.isoformat()
                })
                
            return Response(data, status=200)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class UpdateSellerOrderStatusView(APIView):
    """
    POST /api/orders/seller/<int:pk>/status/
    Body parameters:
    - status: received / packed / out_for_delivery / delivered / cancelled
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            try:
                seller = request.user.seller
            except Exception:
                return Response({'error': 'User is not registered as a seller.'}, status=403)

            try:
                order = CustomerOrder.objects.get(order_id=pk, seller=request.user)
            except CustomerOrder.DoesNotExist:
                return Response({'error': 'Order not found.'}, status=404)
                
            new_status = request.data.get('status')
            if not new_status:
                return Response({'error': 'Status is required.'}, status=400)
                
            valid = ['received', 'packed', 'out_for_delivery', 'delivered', 'cancelled']
            if new_status not in valid:
                return Response({'error': 'Invalid status.'}, status=400)
                
            order.order_status = new_status

            # If delivered COD, set paid
            if new_status == 'delivered' and order.payment_method == 'COD':
                order.payment_status = 'paid'

            order.save()

            # ── Trigger status-change emails asynchronously ────────────────
            if new_status == 'packed':
                send_order_packed_email(order)
            elif new_status == 'out_for_delivery':
                send_order_out_for_delivery_email(order)
            elif new_status == 'delivered':
                send_order_delivered_email(order)
                send_verification_complete_seller_notification(order)
            # ───────────────────────────────────────────────────────

            return Response({
                'message': 'Order status updated successfully.',
                'status': order.order_status
            }, status=200)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


def _build_order_payload(order):
    """Return a standardised dict for a CustomerOrder instance."""
    # Extract customer city from the last parts of the delivery address
    address_parts = [p.strip() for p in order.delivery_address.split(',') if p.strip()]
    # Try second-to-last part as city (format: building, address, city, province)
    customer_city = address_parts[-2] if len(address_parts) >= 2 else (address_parts[-1] if address_parts else '')

    store_city = (order.store.city if order.store and hasattr(order.store, 'city') else '') or ''

    # Estimated delivery window based on city match
    if customer_city and store_city and customer_city.lower() == store_city.lower():
        estimated_delivery = '2-3 business days'
    else:
        estimated_delivery = '5-6 business days'

    # Human-readable payment method
    pm_map = {'stripe': 'Credit/Debit Card', 'COD': 'Cash on Delivery'}
    payment_method_label = pm_map.get(order.payment_method, order.payment_method)

    return {
        'order_id': order.order_id,
        'product_name': order.product_name,
        'quantity': order.quantity,
        'total_amount': float(order.total_amount),
        'payment_method': payment_method_label,
        'payment_status': order.payment_status,
        'order_status': order.order_status,
        'customer_name': order.customer_name,
        'delivery_address': order.delivery_address,
        'created_at': order.created_at.isoformat(),
        'estimated_delivery': estimated_delivery,
        'store_name': order.store.name if order.store else '',
        'store_city': store_city,
        'customer_city': customer_city,
    }


class TrackOrderView(APIView):
    """
    GET /api/orders/track/<order_id>/
    Public endpoint — no authentication required.
    Returns order tracking details for the given order ID.
    """
    permission_classes = []
    authentication_classes = []

    def get(self, request, order_id):
        try:
            order = CustomerOrder.objects.select_related('store').get(order_id=order_id)
        except CustomerOrder.DoesNotExist:
            return Response({'error': 'Order not found. Please check your Order ID.'}, status=404)
        return Response(_build_order_payload(order), status=200)


class MyOrdersView(APIView):
    """
    GET /api/orders/my-orders/
    Authenticated endpoint — returns all orders for the logged-in buyer,
    newest first.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = (
            CustomerOrder.objects
            .filter(customer=request.user)
            .select_related('store')
            .order_by('-created_at')
        )
        return Response([_build_order_payload(o) for o in orders], status=200)
