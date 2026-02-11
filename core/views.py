from decimal import Decimal

from io import BytesIO

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Avg, F, Q, Sum
from django.conf import settings
from django.core.mail import EmailMessage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from django.forms import formset_factory

from .forms import DishForm
from .models import Dish, Order, OrderItem, RestaurantProfile, Restaurant
from .models import SupportTicket


def home(request):
    return render(request, "home.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("app_home")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        auth_username = username
        if "@" in username:
            found_user = User.objects.filter(email__iexact=username).order_by("id").first()
            if found_user:
                auth_username = found_user.username
        user = authenticate(request, username=auth_username, password=password)
        if user:
            login(request, user)
            return redirect("app_home")
        messages.error(request, "Invalid username or password.")
    return render(request, "login.html")


def logout_view(request):
    logout(request)
    return redirect("home")


def admin_logout(request):
    logout(request)
    return redirect("home")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("app_home")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()
        confirm = request.POST.get("confirm", "").strip()
        if not username or not password:
            messages.error(request, "Username and password are required.")
        elif password != confirm:
            messages.error(request, "Passwords do not match.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            auth_user = authenticate(request, username=username, password=password)
            if auth_user:
                login(request, auth_user)
                return redirect("app_home")
            messages.error(request, "Account created, please sign in.")
            return redirect("login")
    return render(request, "register.html")


def app_home(request):
    query = request.GET.get("q", "").strip()
    veg = request.GET.get("veg")
    sort = request.GET.get("sort", "")
    min_rating = request.GET.get("min_rating", "")
    price_band = request.GET.get("price", "")
    restaurant_id = request.GET.get("restaurant", "")
    restaurants = Restaurant.objects.filter(is_active=True).order_by("name")
    dishes = Dish.objects.filter(is_available=True)
    if restaurant_id:
        dishes = dishes.filter(restaurant_id=restaurant_id)
    if query:
        dishes = dishes.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(restaurant__name__icontains=query)
        )
    if veg in {"veg", "nonveg"}:
        dishes = dishes.filter(is_veg=(veg == "veg"))
    if min_rating:
        try:
            dishes = dishes.filter(rating__gte=float(min_rating))
        except ValueError:
            pass
    if price_band == "low":
        dishes = dishes.filter(price__lte=200)
    elif price_band == "mid":
        dishes = dishes.filter(price__gt=200, price__lte=400)
    elif price_band == "high":
        dishes = dishes.filter(price__gt=400)
    if sort == "price_asc":
        dishes = dishes.order_by("price")
    elif sort == "price_desc":
        dishes = dishes.order_by("-price")
    elif sort == "rating":
        dishes = dishes.order_by("-rating")
    dishes = dishes.select_related("restaurant", "category").prefetch_related("images")
    grouped = []
    if restaurant_id:
        from .models import Category
        category_ids = dishes.values_list("category_id", flat=True).distinct()
        categories = Category.objects.filter(id__in=category_ids).order_by("name")
        for category in categories:
            grouped.append(
                {
                    "category": category,
                    "dishes": [d for d in dishes if d.category_id == category.id],
                }
            )
        # Uncategorized
        uncategorized = [d for d in dishes if d.category_id is None]
        if uncategorized:
            grouped.append({"category": None, "dishes": uncategorized})

    return render(
        request,
        "app_home.html",
        {
            "dishes": dishes,
            "grouped": grouped,
            "query": query,
            "filters": {
                "veg": veg or "",
                "sort": sort,
                "min_rating": min_rating,
                "price": price_band,
            },
            "cart_count": _cart_count(_get_cart(request.session)),
            "cart": _get_cart(request.session),
            "restaurants": restaurants,
            "selected_restaurant": restaurant_id,
        },
    )


def _get_cart(session):
    return session.get("cart", {})


def _set_cart(session, cart):
    session["cart"] = cart
    session.modified = True


def _cart_count(cart):
    return sum(cart.values()) if cart else 0


def add_to_cart(request, dish_id):
    if request.method != "POST":
        return redirect("app_home")
    dish = get_object_or_404(Dish, id=dish_id, is_available=True)
    cart = _get_cart(request.session)
    if cart:
        first_id = int(next(iter(cart.keys())))
        first_dish = Dish.objects.filter(id=first_id).select_related("restaurant").first()
        if first_dish and first_dish.restaurant_id != dish.restaurant_id:
            messages.error(
                request,
                "You can only order from one restaurant at a time. Clear the cart to switch.",
            )
            return redirect("cart")
    key = str(dish_id)
    cart[key] = cart.get(key, 0) + 1
    _set_cart(request.session, cart)
    return redirect(request.META.get("HTTP_REFERER", "app_home"))


def add_to_cart_json(request, dish_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    dish = get_object_or_404(Dish, id=dish_id, is_available=True)
    cart = _get_cart(request.session)
    if cart:
        first_id = int(next(iter(cart.keys())))
        first_dish = Dish.objects.filter(id=first_id).select_related("restaurant").first()
        if first_dish and first_dish.restaurant_id != dish.restaurant_id:
            return JsonResponse(
                {
                    "error": "You can only order from one restaurant at a time. Clear the cart to switch.",
                },
                status=400,
            )
    key = str(dish_id)
    cart[key] = cart.get(key, 0) + 1
    _set_cart(request.session, cart)
    return JsonResponse(
        {"dish_id": dish_id, "qty": cart[key], "cart_count": _cart_count(cart)}
    )


def remove_from_cart(request, dish_id):
    cart = _get_cart(request.session)
    key = str(dish_id)
    if key in cart:
        del cart[key]
        _set_cart(request.session, cart)
    return redirect("cart")


def clear_cart(request):
    _set_cart(request.session, {})
    return redirect("app_home")


def update_cart(request, dish_id):
    if request.method != "POST":
        return redirect("cart")
    qty = int(request.POST.get("qty", 1))
    cart = _get_cart(request.session)
    key = str(dish_id)
    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = qty
    _set_cart(request.session, cart)
    return redirect("cart")


def update_cart_json(request, dish_id):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)
    cart = _get_cart(request.session)
    key = str(dish_id)
    qty = int(request.POST.get("qty", 1))
    if qty <= 0:
        cart.pop(key, None)
        qty = 0
    else:
        cart[key] = qty
    _set_cart(request.session, cart)
    return JsonResponse(
        {"dish_id": dish_id, "qty": qty, "cart_count": _cart_count(cart)}
    )


def eta_view(request):
    restaurant_id = request.GET.get("restaurant")
    lat = request.GET.get("lat")
    lng = request.GET.get("lng")
    if not restaurant_id or not lat or not lng:
        return JsonResponse({"error": "Missing parameters"}, status=400)
    restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
    if restaurant.latitude is None or restaurant.longitude is None:
        return JsonResponse({"error": "Restaurant location not set"}, status=400)
    if not settings.GOOGLE_MAPS_API_KEY:
        return JsonResponse({"error": "API key not configured"}, status=400)

    try:
        import json
        import urllib.parse
        import urllib.request

        origins = f"{lat},{lng}"
        destinations = f"{restaurant.latitude},{restaurant.longitude}"
        params = {
            "origins": origins,
            "destinations": destinations,
            "key": settings.GOOGLE_MAPS_API_KEY,
        }
        url = (
            "https://maps.googleapis.com/maps/api/distancematrix/json?"
            + urllib.parse.urlencode(params)
        )
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("status") != "OK":
            return JsonResponse({"error": "API error"}, status=400)
        element = data["rows"][0]["elements"][0]
        if element.get("status") != "OK":
            return JsonResponse({"error": "No route"}, status=400)
        duration_text = element["duration"]["text"]
        duration_value = element["duration"]["value"]
        return JsonResponse(
            {
                "duration_text": duration_text,
                "duration_seconds": duration_value,
                "restaurant": restaurant.name,
            }
        )
    except Exception:
        return JsonResponse({"error": "ETA unavailable"}, status=500)


def cart_view(request):
    cart = _get_cart(request.session)
    dish_ids = [int(d) for d in cart.keys()] if cart else []
    dishes = Dish.objects.filter(id__in=dish_ids).select_related("restaurant")
    items = []
    total = Decimal("0.00")
    for dish in dishes:
        qty = cart.get(str(dish.id), 0)
        line_total = dish.price * qty
        total += line_total
        items.append({"dish": dish, "qty": qty, "line_total": line_total})
    return render(request, "cart.html", {"items": items, "total": total})


@login_required
def checkout(request):
    cart = _get_cart(request.session)
    if not cart:
        return redirect("app_home")

    dish_ids = [int(d) for d in cart.keys()]
    dishes = Dish.objects.filter(id__in=dish_ids)
    total = sum(d.price * cart.get(str(d.id), 0) for d in dishes)

    if request.method == "POST":
        order = Order.objects.create(
            user=request.user,
            customer_name=request.POST.get("name", "Guest"),
            customer_phone=request.POST.get("phone", ""),
            address=request.POST.get("address", ""),
            delivery_latitude=request.POST.get("delivery_latitude") or None,
            delivery_longitude=request.POST.get("delivery_longitude") or None,
            payment_method=request.POST.get("payment", "COD"),
            total_amount=total,
            is_paid=request.POST.get("payment") == "ONLINE",
        )
        for dish in dishes:
            qty = cart.get(str(dish.id), 0)
            if qty:
                OrderItem.objects.create(
                    order=order,
                    dish=dish,
                    quantity=qty,
                    price=dish.price,
                )
        _set_cart(request.session, {})
        if request.user.email:
            pdf_bytes = _build_invoice_pdf(order)
            if pdf_bytes and settings.EMAIL_HOST_USER:
                email = EmailMessage(
                    subject=f"Your FoodBooking Invoice #{order.id}",
                    body="Thanks for your order! Your invoice is attached.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[request.user.email],
                )
                email.attach(f"invoice-{order.id}.pdf", pdf_bytes, "application/pdf")
                email.send(fail_silently=True)
        return redirect("invoice", order_id=order.id)

    return render(request, "checkout.html", {"total": total})


@login_required
def invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    items = []
    for item in order.items.select_related("dish", "dish__restaurant"):
        items.append(
            {
                "dish": item.dish,
                "quantity": item.quantity,
                "price": item.price,
                "line_total": item.price * item.quantity,
            }
        )
    return render(request, "invoice.html", {"order": order, "items": items})


@login_required
def invoice_pdf(request, order_id):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas
    except ImportError:
        messages.error(request, "PDF generation requires ReportLab. Install it and retry.")
        return redirect("invoice", order_id=order_id)

    order = get_object_or_404(Order, id=order_id, user=request.user)
    pdf_bytes = _build_invoice_pdf(order)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice-{order.id}.pdf"'
    return response


def _build_invoice_pdf(order):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas
    except ImportError:
        return None

    items = order.items.select_related("dish", "dish__restaurant")
    items_list = list(items)
    restaurant = items_list[0].dish.restaurant if items_list else None
    subtotal = sum(item.price * item.quantity for item in items_list)
    cgst_rate = Decimal("0.025")
    sgst_rate = Decimal("0.025")
    cgst = subtotal * cgst_rate
    sgst = subtotal * sgst_rate
    grand_total = subtotal + cgst + sgst

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle(f"Invoice-{order.id}")
    pdf.setFillColorRGB(0.97, 0.45, 0.09)
    pdf.rect(0, height - 3 * cm, width, 3 * cm, stroke=0, fill=1)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(2 * cm, height - 2.0 * cm, "FoodBooking Invoice")

    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(2 * cm, height - 3.6 * cm, f"Order ID: {order.id}")
    pdf.drawString(2 * cm, height - 4.3 * cm, f"Date: {order.created_at:%b %d, %Y %H:%M}")
    pdf.drawString(2 * cm, height - 5.0 * cm, f"Customer: {order.customer_name}")
    pdf.drawString(2 * cm, height - 5.7 * cm, f"Phone: {order.customer_phone}")
    pdf.drawString(2 * cm, height - 6.4 * cm, f"Delivery Address: {order.address}")
    pdf.drawString(2 * cm, height - 7.1 * cm, f"Payment: {order.payment_method}")

    if restaurant:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(12 * cm, height - 3.6 * cm, "Restaurant")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(12 * cm, height - 4.2 * cm, restaurant.name)
        pdf.drawString(12 * cm, height - 4.8 * cm, (restaurant.address or "-")[:38])

    y = height - 8.5 * cm
    pdf.setStrokeColor(colors.lightgrey)
    pdf.line(2 * cm, y, width - 2 * cm, y)
    y -= 0.6 * cm

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(2 * cm, y, "Item")
    pdf.drawString(10 * cm, y, "Qty")
    pdf.drawString(12 * cm, y, "Price")
    pdf.drawString(15 * cm, y, "Total")
    y -= 0.4 * cm
    pdf.line(2 * cm, y, width - 2 * cm, y)
    y -= 0.6 * cm

    pdf.setFont("Helvetica", 10)
    for item in items_list:
        if y < 3 * cm:
            pdf.showPage()
            y = height - 2 * cm
        line_total = item.price * item.quantity
        pdf.drawString(2 * cm, y, item.dish.name)
        pdf.drawRightString(11 * cm, y, str(item.quantity))
        pdf.drawRightString(14 * cm, y, f"{item.price}")
        pdf.drawRightString(18 * cm, y, f"{line_total}")
        y -= 0.6 * cm

    y -= 0.4 * cm
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(18 * cm, y, f"Subtotal: {subtotal:.2f}")
    y -= 0.5 * cm
    pdf.drawRightString(18 * cm, y, f"CGST (2.5%): {cgst:.2f}")
    y -= 0.5 * cm
    pdf.drawRightString(18 * cm, y, f"SGST (2.5%): {sgst:.2f}")
    y -= 0.6 * cm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(18 * cm, y, f"Grand Total: {grand_total:.2f}")

    y -= 1.2 * cm
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawString(2 * cm, y, "“Good food is the foundation of genuine happiness.”")
    y -= 0.5 * cm
    pdf.drawString(2 * cm, y, "Thank you for ordering with FoodBooking!")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()


@login_required
def order_history(request):
    orders = (
        Order.objects.filter(user=request.user)
        .order_by("-created_at")
        .prefetch_related("items", "items__dish")
    )
    return render(request, "order_history.html", {"orders": orders})


@login_required
def help_center(request):
    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()
        if subject and message:
            SupportTicket.objects.create(user=request.user, subject=subject, message=message)
            messages.success(request, "Your issue has been submitted.")
            return redirect("help_center")
        messages.error(request, "Please fill all fields.")
    tickets = SupportTicket.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "help_center.html", {"tickets": tickets})


def restaurant_login(request):
    if request.user.is_authenticated:
        return redirect("restaurant_dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        user = authenticate(request, username=username, password=password)
        if user:
            try:
                user.restaurantprofile
            except RestaurantProfile.DoesNotExist:
                messages.error(request, "No restaurant access for this user.")
                return render(request, "restaurant_login.html")
            login(request, user)
            return redirect("restaurant_dashboard")
        messages.error(request, "Invalid username or password.")
    return render(request, "restaurant_login.html")


def _require_restaurant_user(user):
    return hasattr(user, "restaurantprofile")


@login_required
def restaurant_dashboard(request):
    if not _require_restaurant_user(request.user):
        return redirect("restaurant_login")
    profile = request.user.restaurantprofile
    dishes = Dish.objects.filter(restaurant=profile.restaurant).order_by("name")
    today = timezone.localdate()
    today_items = OrderItem.objects.filter(
        dish__restaurant=profile.restaurant,
        order__created_at__date=today,
    )
    today_orders = today_items.values("order_id").distinct().count()
    revenue = today_items.aggregate(total=Sum(F("price") * F("quantity")))["total"] or Decimal("0.00")
    avg_rating = dishes.aggregate(avg=Avg("rating"))["avg"] or 0
    popular_items = (
        OrderItem.objects.filter(dish__restaurant=profile.restaurant)
        .values("dish__name")
        .annotate(qty=Sum("quantity"))
        .order_by("-qty")[:5]
    )
    return render(
        request,
        "restaurant_dashboard.html",
        {
            "profile": profile,
            "dishes": dishes,
            "today_orders": today_orders,
            "revenue": revenue,
            "avg_rating": round(avg_rating, 1) if avg_rating else 0,
            "popular_items": popular_items,
        },
    )


@login_required
def restaurant_add_dish(request):
    if not _require_restaurant_user(request.user):
        return redirect("restaurant_login")
    profile = request.user.restaurantprofile
    from .models import Category
    categories = Category.objects.all().order_by("name")
    DishFormSet = formset_factory(DishForm, extra=1)
    if request.method == "POST":
        formset = DishFormSet(
            request.POST,
            request.FILES,
            form_kwargs={"categories": categories},
        )
        if formset.is_valid():
            created = 0
            for form in formset:
                if form.has_changed():
                    dish = form.save(commit=False)
                    dish.restaurant = profile.restaurant
                    dish.save()
                    created += 1
            if created:
                messages.success(request, f"Added {created} dish(es).")
            else:
                messages.error(request, "No dishes were added.")
            return redirect("restaurant_dashboard")
    else:
        formset = DishFormSet(form_kwargs={"categories": categories})
    return render(
        request,
        "restaurant_add_dish.html",
        {"profile": profile, "formset": formset},
    )
