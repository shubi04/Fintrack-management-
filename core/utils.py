import calendar
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Sum
from django.utils import timezone

from .models import Budget, Category, Transaction
from .templatetags.money import format_inr

DEFAULT_CATEGORIES = [
    ("Food", "🍔", "#F59E0B", "expense"), ("Transport", "🚕", "#3B82F6", "expense"),
    ("Rent", "🏠", "#8B5CF6", "expense"), ("Shopping", "🛍️", "#EC4899", "expense"),
    ("Bills", "💡", "#EF4444", "expense"), ("Health", "💊", "#14B8A6", "expense"),
    ("Entertainment", "🎬", "#F97316", "expense"), ("Other", "🧾", "#6B7280", "expense"),
    ("Salary", "💼", "#10B981", "income"), ("Freelance", "💻", "#06B6D4", "income"),
    ("Gift", "🎁", "#A855F7", "income"),
]

KEYWORDS = {
    "Food": "lunch dinner breakfast food snack coffee tea zomato swiggy restaurant grocery groceries pizza burger meal chai",
    "Transport": "uber ola petrol diesel fuel bus metro train taxi cab auto flight ticket parking",
    "Rent": "rent",
    "Shopping": "shopping amazon flipkart clothes shirt shoes myntra bought",
    "Bills": "bill electricity wifi internet recharge water gas emi insurance",
    "Health": "doctor medicine pharmacy hospital gym medical",
    "Entertainment": "movie netflix spotify game concert party prime hotstar",
    "Salary": "salary stipend paycheck wages",
    "Freelance": "freelance client project",
    "Gift": "gift birthday",
}
INCOME_WORDS = {"salary", "got", "received", "earned", "income", "credited", "bonus", "stipend", "freelance", "refund"}
EXPENSE_WORDS = {"spent", "paid", "bought", "purchase", "gave", "expense", "cost", "pay", "spend"}


def seed_categories(user):
    for name, icon, color, kind in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(user=user, name=name, defaults=dict(icon=icon, color=color, kind=kind, is_default=True))


def month_bounds(d):
    start = d.replace(day=1)
    return start, (start + timedelta(days=32)).replace(day=1)


def add_months(d, n):
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def totals(user, start, end):
    qs = Transaction.objects.filter(user=user, date__gte=start, date__lt=end)
    inc = qs.filter(kind="income").aggregate(s=Sum("amount"))["s"] or Decimal(0)
    exp = qs.filter(kind="expense").aggregate(s=Sum("amount"))["s"] or Decimal(0)
    return inc, exp


def pct_change(cur, prev):
    if not prev:
        return None
    return int(round((cur - prev) / prev * 100))


def category_spend(user, start, end):
    rows = (Transaction.objects.filter(user=user, kind="expense", date__gte=start, date__lt=end)
            .values("category__name", "category__color", "category__icon").annotate(total=Sum("amount")).order_by("-total"))
    return [{"name": r["category__name"] or "Uncategorised", "color": r["category__color"] or "#9CA3AF",
             "icon": r["category__icon"] or "🧾", "total": r["total"]} for r in rows]


def budget_status(user, month_start):
    _, nxt = month_start, add_months(month_start, 1)
    today = timezone.localdate()
    out = []
    for b in Budget.objects.filter(user=user, month=month_start).select_related("category"):
        spent = (Transaction.objects.filter(user=user, kind="expense", category=b.category,
                                            date__gte=month_start, date__lt=nxt).aggregate(s=Sum("amount"))["s"] or Decimal(0))
        pct = int(spent / b.limit * 100) if b.limit else 0
        left = b.limit - spent
        days_left = max((nxt - today).days, 1) if month_start <= today < nxt else 0
        out.append({"b": b, "spent": spent, "pct": pct, "bar": min(pct, 100), "left": left, "days_left": days_left,
                    "per_day": (left / days_left) if days_left and left > 0 else Decimal(0),
                    "level": "ok" if pct < 70 else "warn" if pct < 90 else "bad"})
    return out


def insights(user):
    today = timezone.localdate()
    start, nxt = month_bounds(today)
    pstart = add_months(start, -1)
    inc, exp = totals(user, start, nxt)
    out = []
    if exp:
        days = calendar.monthrange(today.year, today.month)[1]
        forecast = exp / today.day * days
        out.append(f"At this pace you'll spend about {format_inr(forecast, 0)} by month end.")
    cur = {c["name"]: c["total"] for c in category_spend(user, start, nxt)}
    prev = {c["name"]: c["total"] for c in category_spend(user, pstart, start)}
    for name, total in list(cur.items())[:3]:
        ch = pct_change(total, prev.get(name, 0))
        if ch is not None and abs(ch) >= 10:
            out.append(f"You spent {abs(ch)}% {'more' if ch > 0 else 'less'} on {name} than last month.")
    if inc and exp and exp > inc:
        out.append("Your expenses are higher than your income this month.")
    elif inc and exp:
        out.append(f"You've saved {int((inc - exp) / inc * 100)}% of your income this month. Nice.")
    return out[:4]


def parse_quick(text, user):
    """Parse 'Spent 250 on lunch' / 'Got salary 40000 yesterday' into a draft transaction."""
    t = text.lower().strip()
    m = re.search(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakh|l)?\b", t)
    if not m:
        return None
    try:
        amount = Decimal(m.group(1).replace(",", ""))
    except InvalidOperation:
        return None
    mult = {"k": 1000, "thousand": 1000, "lakh": 100000, "l": 100000}.get(m.group(2) or "", 1)
    amount *= mult
    words = set(re.findall(r"[a-z]+", t))
    if not (words & (INCOME_WORDS | EXPENSE_WORDS)):
        return None
    kind = "income" if (words & INCOME_WORDS) and not (words & {"spent", "paid", "bought"}) else "expense"
    d = timezone.localdate()
    if "yesterday" in words:
        d -= timedelta(days=1)
    cats = list(Category.objects.filter(user=user, kind=kind))
    chosen = next((c for c in cats if c.name.lower() in t), None)
    if not chosen:
        for c in cats:
            if words & set(KEYWORDS.get(c.name, "").split()):
                chosen = c
                break
    if not chosen:
        try:
            from .ml import FinancialMLClassifier
            pred_name, conf = FinancialMLClassifier.predict(t, user)
            if pred_name and conf >= 20.0:
                chosen = next((c for c in cats if c.name.lower() == pred_name.lower()), None)
        except Exception:
            pass
    if not chosen:
        chosen = next((c for c in cats if c.name == "Other"), None)
    note = re.sub(r"\s+", " ", re.sub(r"(spent|paid|got|received|earned|on|for|at|rs\.?|₹|inr|today|yesterday)\b", " ", t[:m.start()] + " " + t[m.end():])).strip()
    return {"kind": kind, "amount": str(amount), "category": chosen.id if chosen else None,
            "category_name": f"{chosen.icon} {chosen.name}" if chosen else "Uncategorised",
            "date": d.isoformat(), "note": note.capitalize()[:200]}


def chat_answer(user, text):
    t = text.lower()
    today = timezone.localdate()
    start, nxt = month_bounds(today)
    inc, exp = totals(user, start, nxt)
    draft = parse_quick(text, user)
    if draft:
        return {"type": "confirm", "draft": draft,
                "reply": f"I understood this as {'income' if draft['kind'] == 'income' else 'an expense'}. Please confirm:"}
    if "afford" in t:
        m = re.search(r"(\d[\d,]*(?:\.\d+)?)", t)
        if m:
            want = Decimal(m.group(1).replace(",", ""))
            left = inc - exp
            if left >= want:
                return {"type": "text", "reply": f"Yes. You'd still have **{format_inr(left - want, 0)}** left after that this month."}
            return {"type": "text", "reply": f"That would put you **{format_inr(want - left, 0)}** over what you have left this month ({format_inr(left, 0)})."}
    if "budget" in t:
        st = budget_status(user, start)
        if not st:
            return {"type": "text", "reply": "You have no budgets this month. Open **Budgets** to create one."}
        lines = [f"{s['b'].category.icon} {s['b'].category.name}: **{s['pct']}%** used ({format_inr(s['left'], 0)} left)" for s in st]
        return {"type": "text", "reply": "Your budgets this month:\n" + "\n".join(lines)}
    if "top" in t or "most" in t or "biggest" in t or "category" in t:
        cs = category_spend(user, start, nxt)[:5]
        if not cs:
            return {"type": "text", "reply": "No expenses recorded this month yet."}
        return {"type": "text", "reply": "Top spending this month:\n" + "\n".join(f"{c['icon']} {c['name']}: **{format_inr(c['total'], 0)}**" for c in cs)}
    if "week" in t:
        w0 = today - timedelta(days=today.weekday())
        this, _ = totals_exp(user, w0, today + timedelta(days=1)), None
        last = totals_exp(user, w0 - timedelta(days=7), w0)
        ch = pct_change(this, last)
        extra = "" if ch is None else f" That's {abs(ch)}% {'more' if ch > 0 else 'less'} than last week."
        return {"type": "text", "reply": f"This week you've spent **{format_inr(this, 0)}**.{extra}"}
    if "forecast" in t or "predict" in t or "pace" in t:
        try:
            from .ml import forecast_expenses
            f = forecast_expenses(user)
            direction = "accelerating upwards" if f["trend_direction"] == "accelerating" else "steady"
            return {"type": "text", "reply": f"🤖 **ML Forecast:** At your current spending velocity ({format_inr(f['daily_velocity'], 0)}/day), "
                                             f"you are projected to reach **{format_inr(f['forecast_total'], 0)}** by month-end. "
                                             f"Trend velocity is {direction} with {f['days_left']} days remaining."}
        except Exception:
            pass
    if "anomal" in t or "unusual" in t or "spike" in t:
        try:
            from .ml import detect_anomalies
            anoms = detect_anomalies(user)
            if not anoms:
                return {"type": "text", "reply": "✅ **ML Anomaly Scan:** No unusual spending spikes detected across your categories this month."}
            lines = [f"• **{format_inr(a['amount'], 0)}** on {a['category']} ({a['title']}) - {a['z_score']}σ above normal" for a in anoms]
            return {"type": "text", "reply": "⚠️ **ML Anomaly Detected:** Found unusual spending:\n" + "\n".join(lines)}
        except Exception:
            pass
    if any(w in t for w in ("summary", "month", "overview", "how am i")):
        tips = insights(user)
        body = f"This month: income **{format_inr(inc, 0)}**, expenses **{format_inr(exp, 0)}**, net **{format_inr(inc - exp, 0)}**."
        return {"type": "text", "reply": body + ("\n" + "\n".join("• " + i for i in tips) if tips else "")}
    return {"type": "text", "reply": "I can help with: **Monthly summary**, **ML Forecast**, **Detect anomalies**, **Top spending**, **Check budgets**, "
                                     "\"Can I afford 5000?\", or add entries like **Spent 250 on lunch**."}


def totals_exp(user, start, end):
    return Transaction.objects.filter(user=user, kind="expense", date__gte=start, date__lt=end).aggregate(s=Sum("amount"))["s"] or Decimal(0)
