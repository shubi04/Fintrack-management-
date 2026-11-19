import csv,json
from datetime import date
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse,HttpResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import RegisterForm,TransactionForm,CategoryForm,BudgetForm
from .models import Transaction,Category,Budget
from .services import month_summary,financial_summary,budget_rows
DEFAULT=[('Food & Dining','expense','#10b981'),('Shopping','expense','#f59e0b'),('Transport','expense','#3b82f6'),('Bills & Utilities','expense','#8b5cf6'),('Education','expense','#06b6d4'),('Entertainment','expense','#ec4899'),('Healthcare','expense','#ef4444'),('Rent','expense','#64748b'),('Salary','income','#10b981'),('Other Income','income','#0d9488')]
def seed(user):
 for n,k,c in DEFAULT:Category.objects.get_or_create(user=user,name=n,kind=k,defaults={'color':c})
def home(request):return redirect('dashboard' if request.user.is_authenticated else 'login')
def register(request):
 if request.user.is_authenticated:return redirect('dashboard')
 form=RegisterForm(request.POST or None)
 if request.method=='POST' and form.is_valid():
  u=form.save();seed(u);login(request,u);messages.success(request,'Your FinTrack account is ready.');return redirect('dashboard')
 return render(request,'registration/register.html',{'form':form})
@login_required
def dashboard(request):
 d=timezone.localdate(); sm=month_summary(request.user,d); alltime=financial_summary(request.user); recent=Transaction.objects.filter(user=request.user).select_related('category')[:6]
 cats=list(Transaction.objects.filter(user=request.user,kind='expense',date__year=d.year,date__month=d.month).values('category__name').annotate(total=Sum('amount')).order_by('-total'))
 labels=[];ins=[];outs=[]
 for off in range(5,-1,-1):
  ix=d.month-1-off;y=d.year+ix//12;m=ix%12+1;labels.append(date(y,m,1).strftime('%b'));qs=Transaction.objects.filter(user=request.user,date__year=y,date__month=m)
  ins.append(float(qs.filter(kind='income').aggregate(v=Sum('amount'))['v'] or 0));outs.append(float(qs.filter(kind='expense').aggregate(v=Sum('amount'))['v'] or 0))
 return render(request,'core/dashboard.html',{'summary':sm,'alltime':alltime,'recent':recent,'categories':cats,'months_json':json.dumps(labels),'income_json':json.dumps(ins),'expense_json':json.dumps(outs),'budget_rows':budget_rows(request.user,d)})
@login_required
def transactions(request):
 qs=Transaction.objects.filter(user=request.user).select_related('category');q=request.GET.get('q','').strip();kind=request.GET.get('kind','')
 if q:qs=qs.filter(title__icontains=q)
 if kind in ('income','expense'):qs=qs.filter(kind=kind)
 return render(request,'core/transactions.html',{'transactions':qs,'q':q,'kind':kind})
@login_required
def transaction_add(request):
 f=TransactionForm(request.POST or None,user=request.user)
 if request.method=='POST' and f.is_valid():o=f.save(commit=False);o.user=request.user;o.save();messages.success(request,'Transaction saved.');return redirect('transactions')
 return render(request,'core/transaction_form.html',{'form':f,'heading':'Add transaction'})
@login_required
def transaction_edit(request,pk):
 o=get_object_or_404(Transaction,pk=pk,user=request.user);f=TransactionForm(request.POST or None,instance=o,user=request.user)
 if request.method=='POST' and f.is_valid():f.save();messages.success(request,'Transaction updated.');return redirect('transactions')
 return render(request,'core/transaction_form.html',{'form':f,'heading':'Edit transaction'})
@login_required
@require_POST
def transaction_delete(request,pk):get_object_or_404(Transaction,pk=pk,user=request.user).delete();messages.success(request,'Transaction deleted.');return redirect('transactions')
@login_required
def categories(request):
 f=CategoryForm(request.POST or None)
 if request.method=='POST' and f.is_valid():
  o=f.save(commit=False);o.user=request.user
  try:o.save();messages.success(request,'Category created.');return redirect('categories')
  except Exception:f.add_error('name','This category already exists for this type.')
 return render(request,'core/categories.html',{'form':f,'categories':Category.objects.filter(user=request.user)})
@login_required
def budgets(request):
 f=BudgetForm(request.POST or None,user=request.user)
 if request.method=='POST' and f.is_valid():
  o=f.save(commit=False);o.user=request.user
  try:o.save();messages.success(request,'Budget saved.');return redirect('budgets')
  except Exception:f.add_error(None,'A budget already exists for this category and month.')
 return render(request,'core/budgets.html',{'form':f,'rows':budget_rows(request.user)})
@login_required
def analytics(request):
 d=timezone.localdate();s=month_summary(request.user,d);cats=Transaction.objects.filter(user=request.user,kind='expense',date__year=d.year,date__month=d.month).values('category__name').annotate(total=Sum('amount')).order_by('-total')
 return render(request,'core/analytics.html',{'summary':s,'categories':cats})
@login_required
def export_csv(request):
 r=HttpResponse(content_type='text/csv');r['Content-Disposition']='attachment; filename="fintrack-transactions.csv"';w=csv.writer(r);w.writerow(['Date','Title','Type','Category','Payment Method','Amount','Note'])
 for t in Transaction.objects.filter(user=request.user).select_related('category'):w.writerow([t.date,t.title,t.kind,t.category.name if t.category else '',t.payment_method,t.amount,t.note])
 return r
@login_required
def settings_page(request):return render(request,'core/settings.html')
@login_required
@require_POST
def chat_api(request):
 try:p=json.loads(request.body.decode())
 except Exception:return JsonResponse({'error':'Invalid request.'},status=400)
 msg=str(p.get('message','')).strip()[:1000]
 if not msg:return JsonResponse({'error':'Type a question first.'},status=400)
 from .services import chatbot_answer
 return JsonResponse({'reply':chatbot_answer(request.user,msg)})
