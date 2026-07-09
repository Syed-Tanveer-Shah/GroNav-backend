from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.views.decorators.cache import cache_page
from ..services.products.seller_views import (
    RegisterOnlineSellerView,
    RegisterPhysicalSellerView,
    check_email,
)
from .views import (
    contact_view,
    ContactMessageListCreateAPIView,
    ProductListView,
    CategoryListView,
    CityListView,
    StoreListAPIView,
    StoreDetailAPIView,
    StoreLocationListAPIView,
    save_shopping_list,
    UserShoppingListView,
    get_categories,
    get_category_location,
    StoreViewSet,
    ProductViewSet,
    admin_dashboard_summary,
    ProductDetailAPIView,
    ProductRatingView,
    StoreRatingView,
    BuyerLoginView,
    SellerLoginView,
    CustomPasswordResetView,
)
from dj_rest_auth.views import PasswordResetConfirmView



from .seller_dashboard_views import (
    SellerOverviewAPIView,
    SellerAnalyticsVisitorsAPIView,
    SellerAnalyticsPeakHoursAPIView,
    SellerAnalyticsHeatmapAPIView,
    SellerAnalyticsJourneyAPIView,
    SellerAnalyticsBestTimesAPIView,
    SellerAnalyticsCompetitorPricesAPIView,
    SellerAnalyticsRatingsBreakdownAPIView,
    SellerAnalyticsTopProductsAPIView,
    SellerStoreAPIView,
    SellerStoreToggleAPIView,
    SellerDeliveryRadiusAPIView,
    SellerProductsAPIView,
    SellerProductDetailAPIView,
    SellerProductBulkConfirmAPIView,
    SellerOrdersAPIView,
    SellerOrderDetailAPIView,
    SellerOrderStatusAPIView,
    SellerReturnsAPIView,
    SellerReturnActionAPIView,
    SellerVerificationAPIView,
    SellerStoreRatingsAPIView,
    SellerProductRatingsAPIView,
    SellerSettingsPasswordAPIView,
    SellerSettingsDeleteAccountAPIView,
    SellerLoginAPIView,
    TrackProductViewAPIView,
    TrackStoreViewAPIView,
    TrackJourneyAPIView,
    TrackHeatmapAPIView,
    SellerCategoryListCreateAPIView,
    SellerCategoryDetailAPIView,
    ProductStoreDetailAPIView,
    BulkImportView,
    SellerNotificationsAPIView,
    SellerNotificationReadAPIView,
)

from .payment_views import CreatePaymentIntentView

router = DefaultRouter()
router.register(r'api/admin/stores', StoreViewSet, basename='admin-stores')
router.register(r'api/admin/inventory', ProductViewSet, basename='admin-inventory')

urlpatterns = [
    # Auth
    path('accounts/', include('allauth.urls')),
    path('auth/', include('dj_rest_auth.urls')),
    path('auth/registration/', include('dj_rest_auth.registration.urls')),
    path('api/auth/password/reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('api/auth/password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),

    # Orders
    path('api/orders/', include('src.api.order_urls')),

    # Contact
    path('contact/', contact_view, name='contact'),
    path('api/contact/', ContactMessageListCreateAPIView.as_view(), name='api-contact'),

    # Products & Categories
    path('api/products/', cache_page(30)(ProductListView.as_view()), name='product-list'),
    path('api/categories/', cache_page(300)(CategoryListView.as_view()), name='category-list'),
    path('api/cities/', cache_page(3600)(CityListView.as_view()), name='city-list'),
    path('api/products/<int:pk>/', ProductDetailAPIView.as_view(), name='product-detail-view'),


    # Stores
    path('api/stores/', StoreListAPIView.as_view(), name='store-list'),
    path('api/stores/<int:pk>/', StoreDetailAPIView.as_view(), name='store-detail'),
    path('api/location/', StoreLocationListAPIView.as_view(), name='location'),
    path('product-location/<str:product_name>/', get_category_location, name="product-location"),

    # Shopping List
    path("save-shopping-list/", save_shopping_list, name="save-shopping-list"),
    path("history-list/", UserShoppingListView.as_view(), name="user-shopping-list"),
    path('admin/get-categories/', get_categories, name='get_categories'),
    path('api/admin/dashboard/', admin_dashboard_summary, name='admin-dashboard'),

    # Seller Registration & Auth
    path('api/seller/register/online/', RegisterOnlineSellerView.as_view(), name='seller-register-online'),
    path('api/seller/register/physical/', RegisterPhysicalSellerView.as_view(), name='seller-register-physical'),
    path('api/seller/check-email/', check_email, name='seller-check-email'),
    path('api/seller/login/', SellerLoginAPIView.as_view(), name='seller-login'),

    # Seller Dashboard - Overview
    path('api/seller/overview/', SellerOverviewAPIView.as_view(), name='seller-overview'),

    # Seller Dashboard - Analytics
    path('api/seller/analytics/visitors/', SellerAnalyticsVisitorsAPIView.as_view(), name='seller-analytics-visitors'),
    path('api/seller/analytics/peak-hours/', SellerAnalyticsPeakHoursAPIView.as_view(), name='seller-analytics-peak-hours'),
    path('api/seller/analytics/heatmap/', SellerAnalyticsHeatmapAPIView.as_view(), name='seller-analytics-heatmap'),
    path('api/seller/analytics/journey/', SellerAnalyticsJourneyAPIView.as_view(), name='seller-analytics-journey'),
    path('api/seller/analytics/best-times/', SellerAnalyticsBestTimesAPIView.as_view(), name='seller-analytics-best-times'),
    path('api/seller/analytics/competitor-prices/', SellerAnalyticsCompetitorPricesAPIView.as_view(), name='seller-analytics-competitor-prices'),
    path('api/seller/analytics/ratings-breakdown/', SellerAnalyticsRatingsBreakdownAPIView.as_view(), name='seller-analytics-ratings-breakdown'),
    path('api/seller/analytics/top-products/', SellerAnalyticsTopProductsAPIView.as_view(), name='seller-analytics-top-products'),

    # Seller Dashboard - Store
    path('api/seller/store/', SellerStoreAPIView.as_view(), name='seller-store'),
    path('api/seller/store/toggle/', SellerStoreToggleAPIView.as_view(), name='seller-store-toggle'),
    path('api/seller/store/delivery-radius/', SellerDeliveryRadiusAPIView.as_view(), name='seller-delivery-radius'),

    # Seller Dashboard - Products
    path('api/seller/products/', SellerProductsAPIView.as_view(), name='seller-products'),
    path('api/seller/products/<int:product_id>/', SellerProductDetailAPIView.as_view(), name='seller-product-detail'),
    path('api/seller/products/bulk-confirm/', SellerProductBulkConfirmAPIView.as_view(), name='seller-products-bulk-confirm'),

    # Seller Dashboard - Orders
    path('api/seller/orders/', SellerOrdersAPIView.as_view(), name='seller-orders'),
    path('api/seller/orders/<int:pk>/', SellerOrderDetailAPIView.as_view(), name='seller-order-detail'),
    path('api/seller/orders/<int:pk>/status/', SellerOrderStatusAPIView.as_view(), name='seller-order-status'),
    path('api/seller/orders/returns/', SellerReturnsAPIView.as_view(), name='seller-returns'),
    path('api/seller/orders/returns/<int:pk>/action/', SellerReturnActionAPIView.as_view(), name='seller-return-action'),

    # Seller Dashboard - Verification
    path('api/seller/verification/', SellerVerificationAPIView.as_view(), name='seller-verification'),

    # Seller Dashboard - Ratings
    path('api/seller/ratings/store/', SellerStoreRatingsAPIView.as_view(), name='seller-store-ratings'),
    path('api/seller/ratings/products/', SellerProductRatingsAPIView.as_view(), name='seller-product-ratings'),

    # Public Rating Endpoints
    path('api/ratings/store/<int:store_id>/', StoreRatingView.as_view(), name='public-store-rating'),
    path('api/ratings/product/<int:product_id>/', ProductRatingView.as_view(), name='public-product-rating'),

    # Seller Settings
    path('api/seller/settings/password/', SellerSettingsPasswordAPIView.as_view(), name='seller-settings-password'),
    path('api/seller/settings/account/', SellerSettingsDeleteAccountAPIView.as_view(), name='seller-settings-delete'),

    # Seller Categories
    path('api/seller/categories/', SellerCategoryListCreateAPIView.as_view(), name='seller-categories'),
    path('api/seller/categories/<int:pk>/', SellerCategoryDetailAPIView.as_view(), name='seller-category-detail'),

    # Tracking
    path('api/track/product-view/', TrackProductViewAPIView.as_view(), name='track-product-view'),
    path('api/track/store-view/', TrackStoreViewAPIView.as_view(), name='track-store-view'),
    path('api/track/journey/', TrackJourneyAPIView.as_view(), name='track-journey'),
    path('api/track/heatmap/', TrackHeatmapAPIView.as_view(), name='track-heatmap'),
    path('api/product/<int:product_id>/store/', ProductStoreDetailAPIView.as_view(), name='product-store-detail'),
    path('api/seller/products/bulk-import/', BulkImportView.as_view()),
    path('api/auth/buyer-login/', BuyerLoginView.as_view()),
    path('api/auth/seller-login/', SellerLoginView.as_view()),

    # Notifications
    path('api/seller/notifications/', SellerNotificationsAPIView.as_view()),
    path('api/seller/notifications/<int:pk>/read/', SellerNotificationReadAPIView.as_view()),

    # Payment (Stripe)
    path('api/payment/create-payment-intent', CreatePaymentIntentView.as_view(), name='create-payment-intent'),
]


urlpatterns += router.urls
