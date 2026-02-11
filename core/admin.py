from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, User

from .models import Category, Dish, DishImage, Order, OrderItem, Restaurant, RestaurantProfile, SupportTicket

admin.site.site_header = "FoodBooking Admin"
admin.site.site_title = "FoodBooking Admin Portal"
admin.site.index_title = "Operations Dashboard"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "image")
    list_display_links = ("name",)
    list_filter = ("is_active",)
    search_fields = ("name",)
    list_editable = ("is_active",)
    ordering = ("name",)
    fieldsets = (
        ("Restaurant Info", {"fields": ("name", "address", "image")}),
        ("Location", {"fields": ("latitude", "longitude")}),
        ("Status", {"fields": ("is_active",)}),
    )


@admin.register(RestaurantProfile)
class RestaurantProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "restaurant", "role")
    list_filter = ("role", "restaurant")
    search_fields = ("user__username", "restaurant__name")


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "price", "rating", "is_veg", "is_available", "image")
    list_display_links = ("name",)
    list_filter = ("is_veg", "is_available", "restaurant")
    search_fields = ("name", "restaurant__name")
    list_editable = ("price", "is_available")
    ordering = ("name",)
    fieldsets = (
        ("Dish Details", {"fields": ("name", "description", "image", "price", "rating")}),
        ("Associations", {"fields": ("restaurant", "category")}),
        ("Flags", {"fields": ("is_veg", "is_available")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        try:
            profile = request.user.restaurantprofile
        except RestaurantProfile.DoesNotExist:
            return qs.none()
        return qs.filter(restaurant=profile.restaurant)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "restaurant" and not request.user.is_superuser:
            try:
                profile = request.user.restaurantprofile
                kwargs["queryset"] = Restaurant.objects.filter(id=profile.restaurant_id)
            except RestaurantProfile.DoesNotExist:
                kwargs["queryset"] = Restaurant.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(DishImage)
class DishImageAdmin(admin.ModelAdmin):
    list_display = ("dish", "image")
    search_fields = ("dish__name",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        try:
            profile = request.user.restaurantprofile
        except RestaurantProfile.DoesNotExist:
            return qs.none()
        return qs.filter(dish__restaurant=profile.restaurant)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "dish" and not request.user.is_superuser:
            try:
                profile = request.user.restaurantprofile
                kwargs["queryset"] = Dish.objects.filter(restaurant=profile.restaurant)
            except RestaurantProfile.DoesNotExist:
                kwargs["queryset"] = Dish.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("price",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "customer_phone", "total_amount", "is_paid", "created_at")
    list_display_links = ("id",)
    list_filter = ("is_paid", "payment_method")
    search_fields = ("customer_name", "customer_phone")
    inlines = [OrderItemInline]
    readonly_fields = ("created_at", "total_amount")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "subject", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("subject", "user__username")
    ordering = ("-created_at",)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    pass


try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

admin.site.register(Group)

# Register your models here.
