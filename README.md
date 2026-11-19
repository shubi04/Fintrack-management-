# FinTrack AI — Smart Expense Management System

Django personal finance tracker with login/registration, dashboard, income/expense transactions, categories, monthly budgets, charts, CSV export and a floating chatbot.

## Run locally
Requires Python 3.10+.

```bash
cd FinTrack_AI
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux/Termux: source .venv/bin/activate
pip install -r requirements.txt
# Copy .env.example to .env and change SECRET_KEY
python manage.py makemigrations core
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```
Open http://127.0.0.1:8000/ and register. Default categories are created for each new user.

## Chatbot
Core financial questions are answered by Python using the logged-in user's database records. Optional AI explanations can be enabled by adding OPENAI_API_KEY to .env. The key stays server-side. The app works without the key using built-in responses.

## Admin
`python manage.py createsuperuser`, then visit `/admin/`.

## Deployment
A WSGI host such as Render can run `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate` as the build command and `gunicorn fintrack.wsgi:application` as the start command. Configure SECRET_KEY, DEBUG=False, ALLOWED_HOSTS, DATABASE_URL (PostgreSQL recommended) and CSRF_TRUSTED_ORIGINS. Use persistent PostgreSQL storage; ephemeral SQLite deployments can lose data.

## Production checklist
Set a unique SECRET_KEY, DEBUG=False, correct hosts and HTTPS; configure email for password reset; add privacy/terms pages and security-test before real financial use. The balance is recorded net income minus recorded expenses, not a live bank balance.

## Visual theme
- Midnight plum sidebar with violet gradient navigation.
- Soft lavender/ivory dashboard canvas and white cards.
- Violet chart accents, subtle shadows, rounded panels and responsive mobile layout.
- Matching login, registration and floating chatbot styling.

White theme: white sidebar, white cards, lavender highlights and soft gray background.
