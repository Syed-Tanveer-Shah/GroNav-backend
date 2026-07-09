from django import forms
from .models import Product, ProductDetails, Store

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If editing an existing product
        if self.instance and self.instance.pk and self.instance.store:
            self.fields['details'].queryset = ProductDetails.objects.filter(
                category__in=self.instance.store.categories.all()
            )
        
        # If creating a new product and store is selected
        if 'store' in self.data:
            try:
                store_id = int(self.data.get('store'))
                store = Store.objects.get(id=store_id)
                self.fields['details'].queryset = ProductDetails.objects.filter(
                    category__in=store.categories.all()
                )
            except (ValueError, TypeError, Store.DoesNotExist):
                pass