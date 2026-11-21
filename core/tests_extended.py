import json
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from core import utils
from core.models import Budget, Category, Transaction

User = get_user_model()


class ExtendedFinTrackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("tester@example.com", "tester@example.com", "SecurePass123!", first_name="Tester")
        utils.seed_categories(self.user)
        self.client.login(username="tester@example.com", password="SecurePass123!")

    def test_pwa_endpoints(self):
        # Manifest
        res = self.client.get("/manifest.json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/json")
        data = res.json()
        self.assertEqual(data["name"], "FinTrack AI")

        # Service Worker
        res = self.client.get("/sw.js")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/javascript")
        self.assertIn("fintrack-v1", res.content.decode("utf-8"))

        # Health check
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content.decode("utf-8"), "ok")

    def test_category_management(self):
        # Create category
        res = self.client.post(reverse("categories"), {
            "name": "Subscriptions", "icon": "📺", "color": "#123456", "kind": "expense"
        })
        self.assertEqual(res.status_code, 302)
        cat = Category.objects.get(user=self.user, name="Subscriptions")
        self.assertEqual(cat.icon, "📺")

        # Duplicate category name error
        res = self.client.post(reverse("categories"), {
            "name": "subscriptions", "icon": "📺", "color": "#123456", "kind": "expense"
        })
        self.assertEqual(res.status_code, 302)
        self.assertEqual(Category.objects.filter(user=self.user, name__iexact="subscriptions").count(), 1)

        # Create a transaction with this category
        tx = Transaction.objects.create(user=self.user, kind="expense", amount=199, category=cat, date=date.today(), note="Netflix")

        # Attempt to delete category without force -> should redirect with ?confirm
        res = self.client.post(reverse("category_delete", args=[cat.pk]))
        self.assertEqual(res.status_code, 302)
        self.assertIn(f"?confirm={cat.pk}", res.url)
        self.assertTrue(Category.objects.filter(pk=cat.pk).exists())

        # Now delete with force -> category deleted, transaction retained with category=None
        res = self.client.post(reverse("category_delete", args=[cat.pk]), {"force": "1"})
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())
        tx.refresh_from_db()
        self.assertIsNone(tx.category)

    def test_budget_operations(self):
        food = Category.objects.get(user=self.user, name="Food")
        today = date.today()
        cur_month = today.replace(day=1)
        prev_month = utils.add_months(cur_month, -1)

        # Create budget for last month
        Budget.objects.create(user=self.user, category=food, month=prev_month, limit=Decimal("5000"))

        # Copy budgets to current month
        res = self.client.post(reverse("budget_copy"))
        self.assertEqual(res.status_code, 302)
        cur_budget = Budget.objects.filter(user=self.user, category=food, month=cur_month).first()
        self.assertIsNotNone(cur_budget)
        self.assertEqual(cur_budget.limit, Decimal("5000"))

        # Save/update budget for current month
        res = self.client.post(reverse("budget_save"), {
            "category": food.pk, "limit": "7500", "month": cur_month.strftime("%Y-%m-%d")
        })
        self.assertEqual(res.status_code, 302)
        cur_budget.refresh_from_db()
        self.assertEqual(cur_budget.limit, Decimal("7500"))

        # Delete budget
        res = self.client.post(reverse("budget_delete", args=[cur_budget.pk]))
        self.assertEqual(res.status_code, 302)
        self.assertFalse(Budget.objects.filter(pk=cur_budget.pk).exists())

    def test_transaction_filtering_and_export(self):
        food = Category.objects.get(user=self.user, name="Food")
        salary = Category.objects.get(user=self.user, name="Salary")
        t1 = Transaction.objects.create(user=self.user, kind="expense", amount=150, category=food, date=date.today(), note="Dinner with friends")
        t2 = Transaction.objects.create(user=self.user, kind="expense", amount=800, category=food, date=date.today() - timedelta(days=5), note="Groceries")
        t3 = Transaction.objects.create(user=self.user, kind="income", amount=50000, category=salary, date=date.today() - timedelta(days=10), note="Monthly stipend")

        # Filter by search note
        res = self.client.get(reverse("transactions") + "?q=Dinner")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Dinner with friends")
        self.assertNotContains(res, "Groceries")

        # Filter by type
        res = self.client.get(reverse("transactions") + "?type=income")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Monthly stipend")
        self.assertNotContains(res, "Dinner with friends")

        # Filter by min and max
        res = self.client.get(reverse("transactions") + "?min=200&max=1000")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Groceries")
        self.assertNotContains(res, "Dinner with friends")

        # Sort amount ascending and descending
        res_asc = self.client.get(reverse("transactions") + "?sort=amount_asc")
        self.assertEqual(res_asc.status_code, 200)
        res_desc = self.client.get(reverse("transactions") + "?sort=amount_desc")
        self.assertEqual(res_desc.status_code, 200)

        # Export filtered CSV
        res = self.client.get(reverse("export_csv") + "?filtered=1&q=Groceries")
        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")
        self.assertIn("Groceries", content)
        self.assertNotIn("Dinner with friends", content)

    def test_settings_profile_update(self):
        # Update name and email
        res = self.client.post(reverse("settings"), {
            "action": "profile",
            "first_name": "UpdatedName",
            "last_name": "TesterSurname",
            "email": "updated@example.com"
        })
        self.assertEqual(res.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "UpdatedName")
        self.assertEqual(self.user.email, "updated@example.com")
        self.assertEqual(self.user.username, "updated@example.com")

        # Update password
        res = self.client.post(reverse("settings"), {
            "action": "password",
            "old_password": "SecurePass123!",
            "new_password1": "NewSecurePass987!",
            "new_password2": "NewSecurePass987!"
        })
        self.assertEqual(res.status_code, 302)
        self.client.logout()
        self.assertTrue(self.client.login(username="updated@example.com", password="NewSecurePass987!"))

        # Account deletion confirmation failure
        res = self.client.post(reverse("settings"), {"action": "delete", "confirm": "WRONG"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

        # Account deletion successful
        res = self.client.post(reverse("settings"), {"action": "delete", "confirm": "DELETE"})
        self.assertEqual(res.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_ai_chat_rate_limiting_and_features(self):
        # Normal chat query
        res = self.client.post(reverse("chat"), json.dumps({"message": "how am i doing"}), content_type="application/json")
        self.assertEqual(res.status_code, 200)

        # Rate limiting: 20 messages per minute
        for _ in range(19):
            self.client.post(reverse("chat"), json.dumps({"message": "test"}), content_type="application/json")
        res_limited = self.client.post(reverse("chat"), json.dumps({"message": "test"}), content_type="application/json")
        self.assertEqual(res_limited.status_code, 429)

        # Afford parsing
        cache.clear()
        food = Category.objects.get(user=self.user, name="Food")
        Transaction.objects.create(user=self.user, kind="income", amount=10000, date=date.today())
        Transaction.objects.create(user=self.user, kind="expense", amount=2000, category=food, date=date.today())
        res_afford = self.client.post(reverse("chat"), json.dumps({"message": "can i afford 3000?"}), content_type="application/json").json()
        self.assertIn("Yes", res_afford["reply"])

        res_cannot_afford = self.client.post(reverse("chat"), json.dumps({"message": "can i afford 20000?"}), content_type="application/json").json()
        self.assertIn("over", res_cannot_afford["reply"])
