from django.contrib import admin
from .models import Category, Transaction, Budget, Goal


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "icon", "color", "kind", "user", "is_default"]
    list_filter = ["kind", "is_default"]
    search_fields = ["name", "user__email", "user__username"]
    ordering = ["user", "kind", "name"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "amount", "category", "user", "date", "created"]
    list_filter = ["kind", "category", "date"]
    search_fields = ["note", "user__email", "user__username", "category__name"]
    date_hierarchy = "date"
    ordering = ["-date", "-id"]


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ["category", "user", "month", "limit"]
    list_filter = ["month", "category"]
    search_fields = ["category__name", "user__email", "user__username"]
    ordering = ["-month", "category__name"]


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "target_amount", "saved_amount", "progress_pct", "target_date"]
    list_filter = ["target_date"]
    search_fields = ["name", "user__email", "user__username"]
    ordering = ["target_date", "-id"]
