from django import template

register = template.Library()


@register.filter
def get_item(cart, dish_id):
    if not cart:
        return None
    return cart.get(str(dish_id))
