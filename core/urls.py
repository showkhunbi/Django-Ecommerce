from django.urls import path

from .views import HomeView, OrderSummaryView, ItemDetailView, CheckoutView, add_to_cart, remove_from_cart, remove_single_item_from_cart, add_single_item_to_cart, PaymentView, add_coupon, RefundFormView

app_name = 'core'

urlpatterns = [
    path("", HomeView.as_view(), name="item_list"),
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("order-summary/", OrderSummaryView.as_view(), name="order-summary"),
    path("product/<slug>/", ItemDetailView.as_view(), name="product_page"),
    path("add-to-cart/<slug>/", add_to_cart, name="add_to_cart"),
    path("add-coupon/", add_coupon, name="add-coupon"),
    path("add-single-item-to-cart/<slug>/",
         add_single_item_to_cart, name="add_single_item_to_cart"),
    path("remove-from-cart/<slug>/", remove_from_cart, name="remove_from_cart"),
    path("remove-single-item_from_cart/<slug>/",
         remove_single_item_from_cart, name="remove_single_item_from_cart"),
    path("payment/<payment_method>/", PaymentView.as_view(), name="payment"),
    path("request-refund", RefundFormView.as_view(), name="request-refund")
]
