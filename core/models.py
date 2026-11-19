from django.conf import settings
from django.db import models
from django.utils import timezone
class Category(models.Model):
 KIND=[('expense','Expense'),('income','Income')]
 user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='finance_categories')
 name=models.CharField(max_length=60); kind=models.CharField(max_length=10,choices=KIND,default='expense'); color=models.CharField(max_length=7,default='#0d9468')
 class Meta:
  ordering=['kind','name']; constraints=[models.UniqueConstraint(fields=['user','name','kind'],name='unique_user_category_kind')]
 def __str__(self): return f'{self.name} ({self.kind})'
class Transaction(models.Model):
 KIND=[('income','Income'),('expense','Expense')]; PAYMENT=[('UPI','UPI'),('Cash','Cash'),('Card','Card'),('Bank','Bank'),('Other','Other')]
 user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='transactions'); title=models.CharField(max_length=120); amount=models.DecimalField(max_digits=12,decimal_places=2); kind=models.CharField(max_length=10,choices=KIND); category=models.ForeignKey(Category,on_delete=models.SET_NULL,null=True,blank=True); date=models.DateField(default=timezone.localdate); payment_method=models.CharField(max_length=10,choices=PAYMENT,default='UPI'); note=models.CharField(max_length=250,blank=True); created_at=models.DateTimeField(auto_now_add=True)
 class Meta: ordering=['-date','-created_at']
 def __str__(self): return f'{self.title} - {self.amount}'
class Budget(models.Model):
 user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='budgets'); category=models.ForeignKey(Category,on_delete=models.CASCADE); month=models.DateField(help_text='Use the first day of the month'); limit_amount=models.DecimalField(max_digits=12,decimal_places=2)
 class Meta:
  ordering=['-month','category__name']; constraints=[models.UniqueConstraint(fields=['user','category','month'],name='unique_user_category_month_budget')]
 def __str__(self): return f'{self.category.name} - {self.month:%b %Y}'
