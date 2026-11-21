from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from . import views as v
from . import api_views as api

router = DefaultRouter()
router.register("categories", api.CategoryViewSet, basename="api-category")
router.register("transactions", api.TransactionViewSet, basename="api-transaction")
router.register("budgets", api.BudgetViewSet, basename="api-budget")
router.register("goals", api.GoalViewSet, basename="api-goal")

urlpatterns = [
    path("", v.dashboard, name="dashboard"),
    path("register/", v.register, name="register"),
    path("login/", v.FinLoginView.as_view(), name="login"),
    path("logout/", v.logout_view, name="logout"),
    path("transactions/", v.transactions, name="transactions"),
    path("transactions/new/", v.tx_save, name="tx_create"),
    path("transactions/<int:pk>/edit/", v.tx_save, name="tx_edit"),
    path("transactions/<int:pk>/delete/", v.tx_delete, name="tx_delete"),
    path("transactions/export/", v.export_csv, name="export_csv"),
    path("transactions/export-pdf/", v.export_pdf, name="export_pdf"),
    path("budgets/", v.budgets, name="budgets"),
    path("budgets/save/", v.budget_save, name="budget_save"),
    path("budgets/copy/", v.budget_copy, name="budget_copy"),
    path("budgets/<int:pk>/delete/", v.budget_delete, name="budget_delete"),
    path("goals/", v.goals, name="goals"),
    path("goals/save/", v.goal_save, name="goal_save"),
    path("goals/<int:pk>/edit/", v.goal_save, name="goal_edit"),
    path("goals/<int:pk>/add/", v.goal_add_money, name="goal_add_money"),
    path("goals/<int:pk>/delete/", v.goal_delete, name="goal_delete"),
    path("categories/", v.categories, name="categories"),
    path("categories/<int:pk>/delete/", v.category_delete, name="category_delete"),
    path("analytics/", v.analytics, name="analytics"),
    path("settings/", v.settings_page, name="settings"),
    path("chat/", v.chat, name="chat"),
    path("chat/confirm/", v.chat_confirm, name="chat_confirm"),
    path("healthz", v.healthz),
    path("manifest.json", v.manifest),
    path("sw.js", v.service_worker),
    # REST API endpoints
    path("api/v1/", include(router.urls)),
    path("api/v1/summary/", api.api_summary, name="api_summary"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
