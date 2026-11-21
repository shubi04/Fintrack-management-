from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.Model):
    KINDS = [("expense", "Expense"), ("income", "Income")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=50)
    icon = models.CharField(max_length=8, default="🏷️")
    color = models.CharField(max_length=7, default="#6C5CE7")
    kind = models.CharField(max_length=7, choices=KINDS, default="expense")
    is_default = models.BooleanField(default=False)

    class Meta:
        unique_together = ("user", "name")
        ordering = ["kind", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Transaction(models.Model):
    KINDS = Category.KINDS
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=7, choices=KINDS, default="expense")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)
    date = models.DateField()
    receipt = models.FileField(upload_to="receipts/", null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["user", "date"]), models.Index(fields=["user", "kind", "date"])]

    @property
    def title(self):
        return self.note or (self.category.name if self.category else "Transaction")


class Budget(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets")
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    month = models.DateField(help_text="First day of the month")
    limit = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("user", "category", "month")
        ordering = ["category__name"]


class Goal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goals")
    name = models.CharField(max_length=80)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    saved_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    target_date = models.DateField()
    icon = models.CharField(max_length=8, default="🎯")
    color = models.CharField(max_length=7, default="#10B981")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["target_date", "-id"]

    def __str__(self):
        return f"{self.name} ({self.progress_pct}%)"

    @property
    def progress_pct(self):
        if not self.target_amount:
            return 0
        return min(int((self.saved_amount / self.target_amount) * 100), 100)

    @property
    def remaining_amount(self):
        return max(Decimal(0), self.target_amount - self.saved_amount)

    @property
    def days_left(self):
        delta = (self.target_date - timezone.localdate()).days
        return max(0, delta)

    @property
    def per_day_needed(self):
        if self.days_left and self.remaining_amount > 0:
            return self.remaining_amount / self.days_left
        return Decimal(0)

