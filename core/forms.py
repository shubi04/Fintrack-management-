from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Transaction,Category,Budget
class RegisterForm(UserCreationForm):
 email=forms.EmailField(required=True); first_name=forms.CharField(max_length=80,required=True)
 class Meta: model=User; fields=('first_name','username','email','password1','password2')
 def save(self,commit=True):
  u=super().save(commit=False); u.email=self.cleaned_data['email']; u.first_name=self.cleaned_data['first_name']
  if commit:u.save()
  return u
class TransactionForm(forms.ModelForm):
 class Meta: model=Transaction; fields=['title','amount','kind','category','date','payment_method','note']; widgets={'date':forms.DateInput(attrs={'type':'date'})}
 def __init__(self,*a,**kw):
  self.user=kw.pop('user',None); super().__init__(*a,**kw)
  if self.user:self.fields['category'].queryset=Category.objects.filter(user=self.user)
class CategoryForm(forms.ModelForm):
 class Meta: model=Category; fields=['name','kind','color']
class BudgetForm(forms.ModelForm):
 class Meta: model=Budget; fields=['category','month','limit_amount']; widgets={'month':forms.DateInput(attrs={'type':'date'})}
 def __init__(self,*a,**kw):
  self.user=kw.pop('user',None); super().__init__(*a,**kw)
  if self.user:self.fields['category'].queryset=Category.objects.filter(user=self.user,kind='expense')
