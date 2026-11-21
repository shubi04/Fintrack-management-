from rest_framework import serializers
from .models import Category, Transaction, Budget, Goal


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "icon", "color", "kind", "is_default"]
        read_only_fields = ["id", "is_default"]


class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_icon = serializers.CharField(source="category.icon", read_only=True)

    class Meta:
        model = Transaction
        fields = ["id", "kind", "amount", "category", "category_name", "category_icon", "date", "note", "receipt", "created"]
        read_only_fields = ["id", "created"]


class BudgetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Budget
        fields = ["id", "category", "category_name", "month", "limit"]
        read_only_fields = ["id"]


class GoalSerializer(serializers.ModelSerializer):
    progress_pct = serializers.IntegerField(read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    days_left = serializers.IntegerField(read_only=True)

    class Meta:
        model = Goal
        fields = ["id", "name", "target_amount", "saved_amount", "target_date", "icon", "color", "progress_pct", "remaining_amount", "days_left", "created"]
        read_only_fields = ["id", "created", "progress_pct", "remaining_amount", "days_left"]
