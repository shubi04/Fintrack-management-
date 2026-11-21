import csv
import json
from datetime import timedelta, datetime as dt
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import utils
from .forms import BudgetForm, CategoryForm, LoginForm, ProfileForm, RegisterForm, TransactionForm, GoalForm
from .models import Budget, Category, Transaction, Goal
from .pdf import generate_financial_pdf
from .ml import forecast_expenses


# ---------- auth ----------
class FinLoginView(LoginView):
    authentication_form = LoginForm
    template_name = "core/login.html"
    redirect_authenticated_user = True


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        utils.seed_categories(user)
        login(request, user, backend="core.backends.EmailOrUsernameBackend")
        messages.success(request, f"Welcome, {user.first_name}! Your account is ready.")
        return redirect("dashboard")
    return render(request, "core/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


def healthz(request):
    return HttpResponse("ok")


# ---------- dashboard ----------
@login_required
def dashboard(request):
    u = request.user
    today = timezone.localdate()
    start, nxt = utils.month_bounds(today)
    pstart = utils.add_months(start, -1)
    inc, exp = utils.totals(u, start, nxt)
    pinc, pexp = utils.totals(u, pstart, start)
    all_inc = Transaction.objects.filter(user=u, kind="income").aggregate(s=Sum("amount"))["s"] or Decimal(0)
    all_exp = Transaction.objects.filter(user=u, kind="expense").aggregate(s=Sum("amount"))["s"] or Decimal(0)
    cards = [
        {"label": "Total balance", "value": all_inc - all_exp, "sub": "Net recorded balance", "hero": True},
        {"label": "Income this month", "value": inc, "sub": "Money received", "trend": utils.pct_change(inc, pinc), "up_good": True},
        {"label": "Expenses this month", "value": exp, "sub": "Money spent", "trend": utils.pct_change(exp, pexp), "up_good": False},
        {"label": "Net savings", "value": inc - exp, "sub": "This month"},
    ]
    labels, inc_s, exp_s = [], [], []
    for i in range(5, -1, -1):
        s = utils.add_months(start, -i)
        a, b = utils.totals(u, s, utils.add_months(s, 1))
        labels.append(s.strftime("%b")); inc_s.append(float(a)); exp_s.append(float(b))
    cats = utils.category_spend(u, start, nxt)
    has_tx = Transaction.objects.filter(user=u).exists()
    try:
        ml_forecast = forecast_expenses(u)
    except Exception:
        ml_forecast = None
    user_goals = Goal.objects.filter(user=u)[:3]
    checklist = [
        ("Add your first transaction", has_tx),
        ("Create your own category", Category.objects.filter(user=u, is_default=False).exists()),
        ("Set a budget", Budget.objects.filter(user=u).exists()),
        ("Track a savings goal", user_goals.exists()),
    ]
    ctx = {
        "cards": cards, "recent": Transaction.objects.filter(user=u).select_related("category")[:5],
        "budgets": utils.budget_status(u, start)[:4], "insights": utils.insights(u),
        "checklist": checklist, "show_checklist": not all(d for _, d in checklist),
        "chart": {"labels": labels, "income": inc_s, "expense": exp_s, "has_data": any(inc_s) or any(exp_s)},
        "donut": {"labels": [c["name"] for c in cats], "values": [float(c["total"]) for c in cats], "colors": [c["color"] for c in cats]},
        "cats": cats, "goals": user_goals, "ml_forecast": ml_forecast,
    }
    return render(request, "core/dashboard.html", ctx)


# ---------- transactions ----------
def filtered_transactions(request):
    qs = Transaction.objects.filter(user=request.user).select_related("category")
    g = request.GET
    if g.get("q"):
        qs = qs.filter(Q(note__icontains=g["q"]) | Q(category__name__icontains=g["q"]))
    if g.get("type") in ("income", "expense"):
        qs = qs.filter(kind=g["type"])
    if g.get("category", "").isdigit():
        qs = qs.filter(category_id=g["category"])
    if g.get("from"):
        qs = qs.filter(date__gte=g["from"])
    if g.get("to"):
        qs = qs.filter(date__lte=g["to"])
    if g.get("min", "").replace(".", "", 1).isdigit():
        qs = qs.filter(amount__gte=g["min"])
    if g.get("max", "").replace(".", "", 1).isdigit():
        qs = qs.filter(amount__lte=g["max"])
    sort = g.get("sort")
    return qs.order_by({"amount_desc": "-amount", "amount_asc": "amount", "oldest": "date"}.get(sort, "-date"), "-id")


@login_required
def transactions(request):
    qs = filtered_transactions(request)
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    today = timezone.localdate()
    groups, last = [], None
    for t in page:
        label = "Today" if t.date == today else "Yesterday" if t.date == today - timedelta(days=1) else t.date.strftime("%d %b %Y")
        if label != last:
            groups.append((label, [])); last = label
        groups[-1][1].append(t)
    params = request.GET.copy(); params.pop("page", None)
    return render(request, "core/transactions.html", {"page": page, "groups": groups, "qs_string": params.urlencode(),
                                                      "f": request.GET, "filtered": bool(params)})


@login_required
@require_POST
def tx_save(request, pk=None):
    inst = get_object_or_404(Transaction, pk=pk, user=request.user) if pk else None
    form = TransactionForm(request.POST, instance=inst, user=request.user)
    if form.is_valid():
        t = form.save(commit=False); t.user = request.user; t.save()
        messages.success(request, "Transaction saved ✓")
    else:
        messages.error(request, next(iter(sum(form.errors.values(), [])), "Please check the form."))
    return redirect(request.POST.get("next") or "transactions")


@login_required
@require_POST
def tx_delete(request, pk):
    get_object_or_404(Transaction, pk=pk, user=request.user).delete()
    messages.success(request, "Transaction deleted")
    return redirect(request.POST.get("next") or "transactions")


@login_required
def export_csv(request):
    qs = filtered_transactions(request) if request.GET.get("filtered") else Transaction.objects.filter(user=request.user).select_related("category")
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="fintrack-transactions.csv"'
    w = csv.writer(resp)
    w.writerow(["Date", "Type", "Category", "Amount", "Note"])
    for t in qs:
        w.writerow([t.date, t.kind, t.category.name if t.category else "", t.amount, t.note])
    return resp


@login_required
def export_pdf(request):
    start = None
    end = None
    if request.GET.get("from"):
        try:
            start = dt.strptime(request.GET["from"], "%Y-%m-%d").date()
        except ValueError:
            pass
    if request.GET.get("to"):
        try:
            end = dt.strptime(request.GET["to"], "%Y-%m-%d").date()
        except ValueError:
            pass
    pdf_buffer = generate_financial_pdf(request.user, start, end)
    resp = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="fintrack-statement.pdf"'
    return resp


# ---------- budgets ----------
@login_required
def budgets(request):
    today = timezone.localdate()
    month = utils.month_bounds(today)[0]
    mp = request.GET.get("month")
    if mp:
        try:
            y, m = map(int, mp.split("-")); month = month.replace(year=y, month=m)
        except ValueError:
            pass
    return render(request, "core/budgets.html", {"items": utils.budget_status(request.user, month), "month": month,
                                                 "prev": utils.add_months(month, -1), "next": utils.add_months(month, 1),
                                                 "exp_cats": Category.objects.filter(user=request.user, kind="expense")})


@login_required
@require_POST
def budget_save(request):
    form = BudgetForm(request.POST, user=request.user)
    if form.is_valid():
        d = form.cleaned_data
        Budget.objects.update_or_create(user=request.user, category=d["category"], month=d["month"].replace(day=1),
                                        defaults={"limit": d["limit"]})
        messages.success(request, "Budget saved ✓")
        return redirect(f"/budgets/?month={d['month'].strftime('%Y-%m')}")
    messages.error(request, "Please choose a category and a valid limit.")
    return redirect("budgets")


@login_required
@require_POST
def budget_delete(request, pk):
    get_object_or_404(Budget, pk=pk, user=request.user).delete()
    messages.success(request, "Budget removed")
    return redirect("budgets")


@login_required
@require_POST
def budget_copy(request):
    cur = utils.month_bounds(timezone.localdate())[0]
    n = 0
    for b in Budget.objects.filter(user=request.user, month=utils.add_months(cur, -1)):
        _, created = Budget.objects.get_or_create(user=request.user, category=b.category, month=cur, defaults={"limit": b.limit})
        n += created
    messages.success(request, f"Copied {n} budget(s) from last month" if n else "Nothing new to copy")
    return redirect("budgets")


# ---------- goals ----------
@login_required
def goals(request):
    user_goals = Goal.objects.filter(user=request.user)
    total_target = sum((g.target_amount for g in user_goals), Decimal(0))
    total_saved = sum((g.saved_amount for g in user_goals), Decimal(0))
    overall_pct = int((total_saved / total_target) * 100) if total_target > 0 else 0
    return render(request, "core/goals.html", {
        "goals": user_goals,
        "total_target": total_target,
        "total_saved": total_saved,
        "overall_pct": overall_pct,
    })


@login_required
@require_POST
def goal_save(request, pk=None):
    inst = get_object_or_404(Goal, pk=pk, user=request.user) if pk else None
    form = GoalForm(request.POST, instance=inst)
    if form.is_valid():
        g = form.save(commit=False)
        g.user = request.user
        g.save()
        messages.success(request, "Goal saved ✓")
    else:
        messages.error(request, next(iter(sum(form.errors.values(), [])), "Invalid goal details."))
    return redirect("goals")


@login_required
@require_POST
def goal_add_money(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    try:
        amt = Decimal(request.POST.get("amount", "0"))
        if amt > 0:
            goal.saved_amount += amt
            goal.save()
            messages.success(request, f"Added ₹{amt} to '{goal.name}' ✓")
        else:
            messages.error(request, "Amount must be positive.")
    except Exception:
        messages.error(request, "Invalid amount.")
    return redirect("goals")


@login_required
@require_POST
def goal_delete(request, pk):
    get_object_or_404(Goal, pk=pk, user=request.user).delete()
    messages.success(request, "Goal deleted")
    return redirect("goals")


# ---------- categories ----------
@login_required
def categories(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False); c.user = request.user
            if Category.objects.filter(user=request.user, name__iexact=c.name).exists():
                messages.error(request, "You already have a category with that name.")
            else:
                c.save(); messages.success(request, "Category added ✓")
        else:
            messages.error(request, "Please check the category details.")
        return redirect("categories")
    cats = Category.objects.filter(user=request.user).annotate(n=Sum("transaction__amount"))
    return render(request, "core/categories.html", {"cats": cats})


@login_required
@require_POST
def category_delete(request, pk):
    c = get_object_or_404(Category, pk=pk, user=request.user)
    n = Transaction.objects.filter(category=c).count()
    if n and not request.POST.get("force"):
        messages.error(request, f"'{c.name}' is used by {n} transaction(s). Delete again to keep them uncategorised.")
        return redirect(f"/categories/?confirm={c.pk}")
    c.delete(); messages.success(request, "Category deleted")
    return redirect("categories")


# ---------- analytics ----------
@login_required
def analytics(request):
    u = request.user
    days = int(request.GET.get("range", 30)) if request.GET.get("range", "30").isdigit() else 30
    days = days if days in (7, 30, 90, 365) else 30
    today = timezone.localdate()
    start, end = today - timedelta(days=days - 1), today + timedelta(days=1)
    pstart, pend = start - timedelta(days=days), start
    inc, exp = utils.totals(u, start, end)
    pinc, pexp = utils.totals(u, pstart, pend)
    cats = utils.category_spend(u, start, end)
    prev = {c["name"]: c["total"] for c in utils.category_spend(u, pstart, pend)}
    tips = []
    for c in cats[:4]:
        ch = utils.pct_change(c["total"], prev.get(c["name"], 0))
        if ch is not None and abs(ch) >= 10:
            tips.append(f"You spent {abs(ch)}% {'more' if ch > 0 else 'less'} on {c['name']} than in the previous {days} days.")
    daily = {t["date"]: float(t["s"]) for t in Transaction.objects.filter(user=u, kind="expense", date__gte=start, date__lt=end)
             .values("date").annotate(s=Sum("amount"))}
    d_labels = [(start + timedelta(days=i)) for i in range(days)]
    if days > 90:  # bucket by month for the 1Y view
        labels, vals, seen = [], [], {}
        for d in d_labels:
            k = d.strftime("%b %y"); seen[k] = seen.get(k, 0) + daily.get(d, 0)
        labels, vals = list(seen), list(seen.values())
    else:
        labels, vals = [d.strftime("%d %b") for d in d_labels], [daily.get(d, 0) for d in d_labels]
    cards = [
        {"label": "Income", "value": inc, "trend": utils.pct_change(inc, pinc), "up_good": True},
        {"label": "Expenses", "value": exp, "trend": utils.pct_change(exp, pexp), "up_good": False},
        {"label": "Net savings", "value": inc - exp},
        {"label": "Savings rate", "pct": int((inc - exp) / inc * 100) if inc else None},
    ]
    return render(request, "core/analytics.html", {
        "cards": cards, "cats": cats[:5], "tips": tips, "days": days, "ranges": [(7, "7D"), (30, "30D"), (90, "3M"), (365, "1Y")],
        "donut": {"labels": [c["name"] for c in cats], "values": [float(c["total"]) for c in cats], "colors": [c["color"] for c in cats]},
        "daily": {"labels": labels, "values": vals}, "has_data": bool(cats or inc)})


# ---------- settings ----------
@login_required
def settings_page(request):
    u = request.user
    pform, pwform = ProfileForm(instance=u), PasswordChangeForm(u)
    old_email = u.email
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "profile":
            pform = ProfileForm(request.POST, instance=u)
            if pform.is_valid():
                obj = pform.save(commit=False)
                if obj.username.lower() == old_email.lower():
                    obj.username = obj.email  # keep email-as-username in sync
                obj.save(); messages.success(request, "Profile updated ✓"); return redirect("settings")
        elif action == "password":
            pwform = PasswordChangeForm(u, request.POST)
            if pwform.is_valid():
                update_session_auth_hash(request, pwform.save()); messages.success(request, "Password changed ✓"); return redirect("settings")
        elif action == "delete":
            if request.POST.get("confirm") == "DELETE":
                u.delete(); logout(request); return redirect("login")
            messages.error(request, "Type DELETE to confirm.")
    return render(request, "core/settings.html", {"pform": pform, "pwform": pwform})


# ---------- AI chat ----------
@login_required
@require_POST
def chat(request):
    key = f"chat:{request.user.id}:{timezone.now():%Y%m%d%H%M}"
    n = cache.get(key, 0)
    if n >= 20:
        return JsonResponse({"type": "text", "reply": "You're sending messages too fast. Please wait a minute."}, status=429)
    cache.set(key, n + 1, 90)
    try:
        text = json.loads(request.body).get("message", "")[:300]
    except (ValueError, AttributeError):
        return JsonResponse({"type": "text", "reply": "Sorry, I couldn't read that."}, status=400)
    return JsonResponse(utils.chat_answer(request.user, text))


@login_required
@require_POST
def chat_confirm(request):
    try:
        d = json.loads(request.body)
        data = {"kind": d["kind"], "amount": d["amount"], "category": d.get("category"), "date": d["date"], "note": d.get("note", "")}
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"ok": False, "reply": "Invalid data."}, status=400)
    form = TransactionForm(data, user=request.user)
    if not form.is_valid():
        return JsonResponse({"ok": False, "reply": "I couldn't save that: " + next(iter(sum(form.errors.values(), [])))}, status=400)
    t = form.save(commit=False); t.user = request.user; t.save()
    return JsonResponse({"ok": True, "reply": "Saved ✓ You can see it under Transactions."})


# ---------- PWA ----------
def manifest(request):
    return JsonResponse({"name": "FinTrack AI", "short_name": "FinTrack", "start_url": "/", "display": "standalone",
                         "background_color": "#F8F7FC", "theme_color": "#6C5CE7",
                         "icons": [{"src": "/static/img/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}]})


def service_worker(request):
    js = """const C='fintrack-v1';
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(C).then(c=>c.addAll(['/static/css/app.css','/static/js/app.js'])))});
self.addEventListener('activate',e=>e.waitUntil(clients.claim()));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;
e.respondWith(fetch(e.request).then(r=>{if(e.request.url.includes('/static/')){const cp=r.clone();caches.open(C).then(c=>c.put(e.request,cp))}return r}).catch(()=>caches.match(e.request)))});"""
    return HttpResponse(js, content_type="application/javascript")
