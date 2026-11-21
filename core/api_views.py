from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone
from .models import Category, Transaction, Budget, Goal
from .serializers import CategorySerializer, TransactionSerializer, BudgetSerializer, GoalSerializer
from . import utils


class BaseUserViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CategoryViewSet(BaseUserViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class TransactionViewSet(BaseUserViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = super().get_queryset().select_related("category")
        kind = self.request.query_params.get("kind")
        if kind in ("income", "expense"):
            qs = qs.filter(kind=kind)
        return qs


class BudgetViewSet(BaseUserViewSet):
    queryset = Budget.objects.all()
    serializer_class = BudgetSerializer


class GoalViewSet(BaseUserViewSet):
    queryset = Goal.objects.all()
    serializer_class = GoalSerializer


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def api_summary(request):
    today = timezone.localdate()
    start, nxt = utils.month_bounds(today)
    inc, exp = utils.totals(request.user, start, nxt)
    all_inc = Transaction.objects.filter(user=request.user, kind="income").aggregate(s=Sum("amount"))["s"] or Decimal(0)
    all_exp = Transaction.objects.filter(user=request.user, kind="expense").aggregate(s=Sum("amount"))["s"] or Decimal(0)
    
    return Response({
        "status": "success",
        "currency": "INR",
        "total_balance": float(all_inc - all_exp),
        "month_income": float(inc),
        "month_expense": float(exp),
        "net_savings": float(inc - exp),
        "savings_rate_pct": int((inc - exp) / inc * 100) if inc > 0 else 0,
        "categories_count": Category.objects.filter(user=request.user).count(),
        "goals_count": Goal.objects.filter(user=request.user).count(),
        "budgets_count": Budget.objects.filter(user=request.user, month=start).count(),
    })
