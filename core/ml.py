"""
FinTrack AI - Machine Learning & NLP Subsystem
Implements:
1. TF-IDF + Multinomial Naive Bayes Natural Language Category Classification.
2. Linear Regression Month-End Expense Forecasting.
3. Statistical Anomaly Detection for Unusual Category Spending.
"""

from decimal import Decimal
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from django.utils import timezone
from django.db.models import Sum, Avg, StdDev

# Baseline training corpus for personal finance expense & income classification
TRAINING_DATA = [
    # Food
    ("lunch with friends at cafe", "Food"),
    ("zomato food delivery dinner", "Food"),
    ("swiggy biryani meal", "Food"),
    ("starbucks coffee and cookies", "Food"),
    ("grocery items from supermarket", "Food"),
    ("vegetables fruits and milk", "Food"),
    ("dominos pizza party", "Food"),
    ("mcdonalds burger fries", "Food"),
    ("office canteen chai snacks", "Food"),
    ("bakery bread cake", "Food"),
    ("restaurant dining weekend", "Food"),
    # Transport
    ("uber ride to office", "Transport"),
    ("ola cab to airport", "Transport"),
    ("petrol fuel refill for car", "Transport"),
    ("diesel fuel bike petrol pump", "Transport"),
    ("metro card recharge daily travel", "Transport"),
    ("flight tickets booking indigo", "Transport"),
    ("irctc train ticket reservation", "Transport"),
    ("bus pass monthly travel", "Transport"),
    ("fastag toll plaza charges", "Transport"),
    ("parking fee mall", "Transport"),
    ("auto rickshaw fare", "Transport"),
    # Rent
    ("house rent transfer to landlord", "Rent"),
    ("apartment monthly rent", "Rent"),
    ("flat society maintenance charges", "Rent"),
    ("pg hostel accommodation fee", "Rent"),
    # Shopping
    ("amazon online order clothes", "Shopping"),
    ("flipkart electronics laptop sleeve", "Shopping"),
    ("myntra shoes sneakers purchase", "Shopping"),
    ("zara jacket trousers shirts", "Shopping"),
    ("shopping at mall clothing brand", "Shopping"),
    ("bought new running shoes", "Shopping"),
    # Bills
    ("electricity bill online payment", "Bills"),
    ("broadband wifi internet recharge", "Bills"),
    ("airtel jio mobile monthly recharge", "Bills"),
    ("water bill municipal corporation", "Bills"),
    ("piped gas cylinder lpg payment", "Bills"),
    ("credit card bill payment", "Bills"),
    ("car bike insurance annual premium", "Bills"),
    ("home loan personal loan emi payment", "Bills"),
    # Health
    ("doctor consultation clinic fee", "Health"),
    ("apollo pharmacy medicines tablet", "Health"),
    ("blood test diagnostic lab scan", "Health"),
    ("gym fitness center annual membership", "Health"),
    ("hospital emergency visit medical bill", "Health"),
    ("dentist dental teeth cleanup", "Health"),
    # Entertainment
    ("netflix monthly premium subscription", "Entertainment"),
    ("pvr cinemas movie tickets popcorn", "Entertainment"),
    ("spotify music subscription plan", "Entertainment"),
    ("hotstar disney ott subscription", "Entertainment"),
    ("steam video games playstation", "Entertainment"),
    ("music concert standup comedy show", "Entertainment"),
    ("club weekend drinks party", "Entertainment"),
    # Salary
    ("monthly company salary credited", "Salary"),
    ("salary paycheck wages bank transfer", "Salary"),
    ("annual performance bonus credited", "Salary"),
    ("internship stipend credited", "Salary"),
    # Freelance
    ("freelance web development project payout", "Freelance"),
    ("client consulting invoice payment received", "Freelance"),
    ("upwork fiverr earnings transferred", "Freelance"),
    # Gift
    ("birthday gift cash from parents", "Gift"),
    ("diwali festive bonus cash gift", "Gift"),
    ("wedding anniversary gift received", "Gift"),
]


class FinancialMLClassifier:
    """
    TF-IDF Vectorizer + Multinomial Naive Bayes Pipeline for Category Prediction.
    Augments base dataset with user historical transactions when available.
    """
    _pipeline = None

    @classmethod
    def get_pipeline(cls, user=None):
        X = [item[0] for item in TRAINING_DATA]
        y = [item[1] for item in TRAINING_DATA]

        # Augment with user historical transactions if user provided
        if user and user.is_authenticated:
            try:
                from .models import Transaction
                user_txs = Transaction.objects.filter(user=user, category__isnull=False).exclude(note="")[:100]
                for tx in user_txs:
                    if len(tx.note.strip()) >= 3:
                        X.append(tx.note)
                        y.append(tx.category.name)
            except Exception:
                pass

        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True, stop_words="english")),
            ("clf", MultinomialNB(alpha=0.5)),
        ])
        pipeline.fit(X, y)
        return pipeline

    @classmethod
    def predict(cls, text, user=None):
        if not text or len(text.strip()) < 2:
            return None, 0.0
        pipeline = cls.get_pipeline(user)
        predicted_cat = pipeline.predict([text])[0]
        probabilities = pipeline.predict_proba([text])[0]
        confidence = float(np.max(probabilities)) * 100.0
        return predicted_cat, round(confidence, 1)


def forecast_expenses(user):
    """
    Fits a Linear Regression model on daily cumulative expense data for current month
    to predict total month-end expense trajectory with confidence.
    """
    from .models import Transaction
    today = timezone.localdate()
    start = today.replace(day=1)
    days_in_month = (today.replace(day=28) + timezone.timedelta(days=4)).replace(day=1) - timezone.timedelta(days=1)
    total_days = days_in_month.day

    # Query daily spend
    daily_qs = (
        Transaction.objects.filter(user=user, kind="expense", date__gte=start, date__lte=today)
        .values("date")
        .annotate(total=Sum("amount"))
        .order_by("date")
    )
    daily_map = {row["date"]: float(row["total"]) for row in daily_qs}

    current_day = today.day
    if current_day < 2 or not daily_map:
        total_so_far = sum(daily_map.values())
        return {
            "forecast_total": total_so_far,
            "projected_variance": 0.0,
            "trend_direction": "stable",
            "daily_velocity": total_so_far / max(1, current_day),
            "days_left": total_days - current_day,
        }

    # Prepare features: X = day number [1..current_day], y = cumulative spending
    X = []
    y = []
    cumulative = 0.0
    for day in range(1, current_day + 1):
        d = start.replace(day=day)
        cumulative += daily_map.get(d, 0.0)
        X.append([day])
        y.append(cumulative)

    reg = LinearRegression()
    reg.fit(X, y)
    predicted_month_end = float(reg.predict([[total_days]])[0])
    predicted_month_end = max(predicted_month_end, cumulative)

    daily_velocity = cumulative / current_day
    slope = float(reg.coef_[0])

    return {
        "forecast_total": round(predicted_month_end, 2),
        "so_far": round(cumulative, 2),
        "daily_velocity": round(daily_velocity, 2),
        "slope": round(slope, 2),
        "trend_direction": "accelerating" if slope > daily_velocity else "steady",
        "days_left": total_days - current_day,
    }


def detect_anomalies(user):
    """
    Flags individual transactions in the past 30 days that are statistically anomalous
    (e.g., > 2.0 standard deviations above the user's category average).
    """
    from .models import Transaction
    today = timezone.localdate()
    cutoff = today - timezone.timedelta(days=30)
    txs = Transaction.objects.filter(user=user, kind="expense", date__gte=cutoff).select_related("category")
    
    anomalies = []
    category_amounts = {}
    for t in txs:
        cat_name = t.category.name if t.category else "Uncategorised"
        category_amounts.setdefault(cat_name, []).append((float(t.amount), t))

    for cat_name, pairs in category_amounts.items():
        if len(pairs) >= 3:
            vals = [p[0] for p in pairs]
            mean = np.mean(vals)
            std = np.std(vals)
            if std > 0:
                for amt, t in pairs:
                    z_score = (amt - mean) / std
                    if z_score >= 2.0:
                        anomalies.append({
                            "title": t.title,
                            "amount": amt,
                            "category": cat_name,
                            "date": t.date,
                            "z_score": round(z_score, 1),
                            "mean": round(mean, 2)
                        })
    return anomalies[:3]
