from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from .models import Transaction,Budget
def month_summary(user,d=None):
 d=d or timezone.localdate(); qs=Transaction.objects.filter(user=user,date__year=d.year,date__month=d.month)
 inc=qs.filter(kind='income').aggregate(v=Sum('amount'))['v'] or Decimal('0'); exp=qs.filter(kind='expense').aggregate(v=Sum('amount'))['v'] or Decimal('0')
 return {'income':inc,'expenses':exp,'savings':inc-exp}
def financial_summary(user):
 qs=Transaction.objects.filter(user=user); inc=qs.filter(kind='income').aggregate(v=Sum('amount'))['v'] or Decimal('0'); exp=qs.filter(kind='expense').aggregate(v=Sum('amount'))['v'] or Decimal('0')
 return {'balance':inc-exp}
def budget_rows(user,d=None):
 d=d or timezone.localdate(); out=[]
 for b in Budget.objects.filter(user=user,month__year=d.year,month__month=d.month).select_related('category'):
  spent=Transaction.objects.filter(user=user,kind='expense',category=b.category,date__year=d.year,date__month=d.month).aggregate(v=Sum('amount'))['v'] or Decimal('0')
  pct=min(int(spent/b.limit_amount*100),999) if b.limit_amount else 0
  out.append({'budget':b,'spent':spent,'remaining':b.limit_amount-spent,'percent':pct})
 return out
def chatbot_answer(user,message):
 from .models import Transaction
 from django.db.models import Sum
 d=timezone.localdate(); s=month_summary(user,d); q=message.lower()
 if any(x in q for x in ['food','dining','category','where did']):
  rows=list(Transaction.objects.filter(user=user,kind='expense',date__year=d.year,date__month=d.month).values('category__name').annotate(total=Sum('amount')).order_by('-total'))
  if rows:return f"Your highest spending category this month is {rows[0]['category__name'] or 'Uncategorised'} at ₹{rows[0]['total']:,.2f}. Total expenses: ₹{s['expenses']:,.2f}."
  return 'No expenses are recorded for this month yet.'
 if any(x in q for x in ['budget','limit','overspend']):
  rows=budget_rows(user,d)
  if not rows:return 'You have not set any budgets for this month. Open Budgets to create one.'
  over=[r for r in rows if r['remaining']<0]
  if over:return 'Over budget: '+', '.join(f"{r['budget'].category.name} by ₹{abs(r['remaining']):,.2f}" for r in over)+'.'
  return 'Your budgets are within their limits. '+ '; '.join(f"{r['budget'].category.name}: ₹{r['spent']:,.0f} of ₹{r['budget'].limit_amount:,.0f}" for r in rows[:4])
 if any(x in q for x in ['save','saving','balance','left']):return f"This month: income ₹{s['income']:,.2f}, expenses ₹{s['expenses']:,.2f}, net savings ₹{s['savings']:,.2f}. Try setting limits for your highest-spending categories."
 if any(x in q for x in ['summary','spent','expense','money']):return f"Month-to-date: income ₹{s['income']:,.2f}, expenses ₹{s['expenses']:,.2f}, net savings ₹{s['savings']:,.2f}. Ask about a category or budget for more detail."
 import os
 if os.getenv('OPENAI_API_KEY'):
  try:
   from openai import OpenAI
   r=OpenAI(api_key=os.getenv('OPENAI_API_KEY')).chat.completions.create(model=os.getenv('OPENAI_MODEL','gpt-4o-mini'),messages=[{'role':'system','content':f"You are FinTrack AI. Do not invent figures. Verified user figures this month: income ₹{s['income']}, expenses ₹{s['expenses']}, net savings ₹{s['savings']}. Give concise general budgeting guidance."},{'role':'user','content':message}],max_tokens=220)
   return r.choices[0].message.content
  except Exception:pass
 return 'I can help with monthly spending, savings, categories and budgets. Try “Summarize my expenses”, “Where did my money go?” or “Am I over budget?”'
