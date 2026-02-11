from django.urls import path

from . import views


urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('app/', views.app_home, name='app_home'),
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:dish_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/add/<int:dish_id>/json/', views.add_to_cart_json, name='add_to_cart_json'),
    path('cart/remove/<int:dish_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:dish_id>/', views.update_cart, name='update_cart'),
    path('cart/update/<int:dish_id>/json/', views.update_cart_json, name='update_cart_json'),
    path('eta/', views.eta_view, name='eta'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('invoice/<int:order_id>/', views.invoice, name='invoice'),
    path('invoice/<int:order_id>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('orders/', views.order_history, name='order_history'),
    path('help/', views.help_center, name='help_center'),
    path('restaurant/login/', views.restaurant_login, name='restaurant_login'),
    path('restaurant/', views.restaurant_dashboard, name='restaurant_dashboard'),
    path('restaurant/dishes/add/', views.restaurant_add_dish, name='restaurant_add_dish'),
]
