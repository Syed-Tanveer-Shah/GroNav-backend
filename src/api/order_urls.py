from django.urls import path
from .order_views import (
    CreateOrderView,
    SellerOrderListView,
    UpdateSellerOrderStatusView,
    TrackOrderView,
    MyOrdersView,
)

urlpatterns = [
    path('create/', CreateOrderView.as_view(), name='order-create'),
    path('seller/', SellerOrderListView.as_view(), name='order-seller-list'),
    path('seller/<int:pk>/status/', UpdateSellerOrderStatusView.as_view(), name='order-update-status'),
    path('track/<int:order_id>/', TrackOrderView.as_view(), name='order-track'),
    path('my-orders/', MyOrdersView.as_view(), name='my-orders'),
]
