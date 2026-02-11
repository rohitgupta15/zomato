from django import forms

from .models import Dish


class DishForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = [
            "name",
            "description",
            "price",
            "rating",
            "category",
            "image",
            "is_veg",
            "is_available",
        ]

    def __init__(self, *args, **kwargs):
        categories = kwargs.pop("categories", None)
        super().__init__(*args, **kwargs)
        if categories is not None:
            self.fields["category"].queryset = categories
