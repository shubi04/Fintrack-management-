import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import utils
from .models import Budget, Category, Transaction
from .templatetags.money import format_inr

User = get_user_model()


class Base(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("a@x.com", "a@x.com", "pass12345!", first_name="Asha")
        utils.seed_categories(self.u)
        self.client.login(username="a@x.com", password="pass12345!")


class ParserTests(Base):
    def test_expense(self):
        d = utils.parse_quick("Spent 250 on lunch", self.u)
        self.assertEqual((d["kind"], d["amount"], d["category_name"]), ("expense", "250", "🍔 Food"))

    def test_income_k(self):
        d = utils.parse_quick("Got salary 40k", self.u)
        self.assertEqual((d["kind"], d["amount"]), ("income", "40000"))
        self.assertIn("Salary", d["category_name"])

    def test_no_intent(self):
        self.assertIsNone(utils.parse_quick("hello there", self.u))

    def test_inr_format(self):
        self.assertEqual(format_inr(100000, 0), "₹1,00,000")
        self.assertEqual(format_inr(1234567.5), "₹12,34,567.50")


class FlowTests(Base):
    def test_register_login_email(self):
        self.client.logout()
        r = self.client.post(reverse("register"), {"first_name": "Bo", "email": "Bo@X.com", "password": "Strong#Pass91"})
        self.assertRedirects(r, reverse("dashboard"))
        self.assertTrue(Category.objects.filter(user__email="bo@x.com").exists())
        self.client.logout()
        self.assertTrue(self.client.login(username="BO@x.com", password="Strong#Pass91"))

    def test_duplicate_email(self):
        self.client.logout()
        r = self.client.post(reverse("register"), {"first_name": "B", "email": "a@x.com", "password": "Strong#Pass91"})
        self.assertContains(r, "already registered")

    def test_all_pages_empty_and_with_data(self):
        food = Category.objects.get(user=self.u, name="Food")
        for with_data in (False, True):
            if with_data:
                Transaction.objects.create(user=self.u, kind="expense", amount=500, category=food, date=date.today(), note="Lunch")
                Budget.objects.create(user=self.u, category=food, month=date.today().replace(day=1), limit=1000)
            for name in ("dashboard", "transactions", "budgets", "categories", "analytics", "settings"):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("analytics") + "?range=365").status_code, 200)
        self.assertEqual(self.client.get(reverse("export_csv")).status_code, 200)

    def test_add_edit_delete_transaction(self):
        food = Category.objects.get(user=self.u, name="Food")
        self.client.post(reverse("tx_create"), {"kind": "expense", "amount": "99", "category": food.id, "date": "2026-11-01", "note": "x"})
        t = Transaction.objects.get()
        self.client.post(reverse("tx_edit", args=[t.pk]), {"kind": "expense", "amount": "120", "category": food.id, "date": "2026-11-01", "note": "y"})
        t.refresh_from_db(); self.assertEqual(t.amount, Decimal("120"))
        self.client.post(reverse("tx_delete", args=[t.pk]))
        self.assertFalse(Transaction.objects.exists())

    def test_cannot_touch_other_users_data(self):
        other = User.objects.create_user("b@x.com", "b@x.com", "pass12345!")
        utils.seed_categories(other)
        t = Transaction.objects.create(user=other, kind="expense", amount=5, date=date.today())
        self.assertEqual(self.client.post(reverse("tx_delete", args=[t.pk])).status_code, 404)
        c = Category.objects.filter(user=other).first()
        self.client.post(reverse("tx_create"), {"kind": "expense", "amount": "5", "category": c.id, "date": "2026-11-01"})
        self.assertFalse(Transaction.objects.filter(user=self.u).exists())

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)

    def test_chat_quick_add(self):
        r = self.client.post(reverse("chat"), json.dumps({"message": "Spent 250 on lunch"}), content_type="application/json").json()
        self.assertEqual(r["type"], "confirm")
        r2 = self.client.post(reverse("chat_confirm"), json.dumps(r["draft"]), content_type="application/json").json()
        self.assertTrue(r2["ok"]); self.assertEqual(Transaction.objects.get().amount, Decimal("250"))
        bad = self.client.post(reverse("chat_confirm"), json.dumps({**r["draft"], "amount": "-5"}), content_type="application/json")
        self.assertEqual(bad.status_code, 400)
        for q in ("Monthly summary", "Top spending", "Check budgets", "Can I afford 5000?", "this week"):
            self.assertEqual(self.client.post(reverse("chat"), json.dumps({"message": q}), content_type="application/json").status_code, 200)
