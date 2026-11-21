from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from .models import Budget, Category, Transaction, Goal

User = get_user_model()


class RegisterForm(forms.Form):
    first_name = forms.CharField(max_length=60, widget=forms.TextInput(attrs={"placeholder": "Your name", "autocomplete": "given-name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Create a password", "autocomplete": "new-password"}))

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("This email is already registered. Try logging in.")
        return email

    def clean_password(self):
        pw = self.cleaned_data["password"]
        validate_password(pw)
        return pw

    def save(self):
        d = self.cleaned_data
        return User.objects.create_user(username=d["email"], email=d["email"], password=d["password"], first_name=d["first_name"].strip())


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Email", widget=forms.TextInput(attrs={"placeholder": "you@example.com", "autocomplete": "username", "autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Your password", "autocomplete": "current-password"}))
    error_messages = {"invalid_login": "Email or password is incorrect.", "inactive": "This account is inactive."}


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["kind", "amount", "category", "date", "note", "receipt"]

    def __init__(self, *a, user=None, **kw):
        super().__init__(*a, **kw)
        self.fields["category"].queryset = Category.objects.filter(user=user)
        self.fields["category"].required = False

    def clean_amount(self):
        a = self.cleaned_data["amount"]
        if a <= 0:
            raise forms.ValidationError("Amount must be more than 0.")
        return a


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "icon", "color", "kind"]


class BudgetForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.none(), empty_label=None)
    limit = forms.DecimalField(min_value=1, max_digits=12, decimal_places=2)
    month = forms.DateField(input_formats=["%Y-%m", "%Y-%m-%d"])

    def __init__(self, *a, user=None, **kw):
        super().__init__(*a, **kw)
        self.fields["category"].queryset = Category.objects.filter(user=user, kind="expense")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def clean_email(self):
        e = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=e).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("That email is used by another account.")
        return e


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ["name", "target_amount", "saved_amount", "target_date", "icon", "color"]

    def clean_target_amount(self):
        a = self.cleaned_data["target_amount"]
        if a <= 0:
            raise forms.ValidationError("Target amount must be greater than 0.")
        return a

