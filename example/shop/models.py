from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=128)
    code = models.SlugField()
    price = models.DecimalField(max_digits=18, decimal_places=2)

    def __str__(self):
        return self.name

    def get_price(self, request):
        return self.price
