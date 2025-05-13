from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib import messages
from .models import Category, Transaction, Budget
from django.db.models import Sum
from datetime import date
import json  # Add this import
from django.core.serializers.json import DjangoJSONEncoder

def signup_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            
            # Create default categories for new user
            Category.objects.bulk_create([
                Category(user=user, name="Salary", category_type="income", color="#4361ee"),
                Category(user=user, name="Freelance", category_type="income", color="#3a0ca3"),
                Category(user=user, name="Investments", category_type="income", color="#7209b7"),
                Category(user=user, name="Food", category_type="expense", color="#f72585"),
                Category(user=user, name="Transport", category_type="expense", color="#4895ef"),
                Category(user=user, name="Entertainment", category_type="expense", color="#4cc9f0"),
            ])
            
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password')
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard(request):
    income = Transaction.objects.filter(user=request.user, transaction_type='income').aggregate(Sum('amount'))['amount__sum'] or 0
    expenses = Transaction.objects.filter(user=request.user, transaction_type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
    balance = income - expenses
    
    recent_transactions = Transaction.objects.filter(user=request.user).order_by('-date')[:5]
    
    context = {
        'income': income,
        'expenses': expenses,
        'balance': balance,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'dashboard.html', context)

@login_required
def income(request):
    if request.method == 'POST':
        try:
            amount = request.POST['amount']
            category_id = request.POST['category']
            description = request.POST['description']
            date = request.POST['date']
            
            category = Category.objects.get(id=category_id, user=request.user)
            Transaction.objects.create(
                user=request.user,
                amount=amount,
                category=category,
                description=description,
                date=date,
                transaction_type='income'
            )
            messages.success(request, "Income added successfully!")
            return redirect('income')
        except Category.DoesNotExist:
            messages.error(request, "Selected category doesn't exist")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    categories = Category.objects.filter(user=request.user, category_type='income')
    incomes = Transaction.objects.filter(
        user=request.user, 
        transaction_type='income'
    ).order_by('-date').select_related('category')
    
    return render(request, 'income.html', {
        'categories': categories,
        'incomes': incomes
    })

@login_required
def expenses(request):
    if request.method == 'POST':
        try:
            amount = request.POST['amount']
            category_id = request.POST['category']
            description = request.POST['description']
            date = request.POST['date']
            
            category = Category.objects.get(id=category_id, user=request.user)
            Transaction.objects.create(
                user=request.user,
                amount=amount,
                category=category,
                description=description,
                date=date,
                transaction_type='expense'
            )
            messages.success(request, "Expense added successfully!")
            return redirect('expenses')
        except Category.DoesNotExist:
            messages.error(request, "Selected category doesn't exist")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    categories = Category.objects.filter(user=request.user, category_type='expense')
    expenses = Transaction.objects.filter(
        user=request.user, 
        transaction_type='expense'
    ).order_by('-date').select_related('category')
    
    return render(request, 'expenses.html', {
        'categories': categories,
        'expenses': expenses
    })

@login_required
def budget(request):
    if request.method == 'POST':
        try:
            category_id = request.POST['category']
            amount = request.POST['amount']
            start_date = request.POST['start_date']
            end_date = request.POST['end_date']
            
            category = Category.objects.get(id=category_id, user=request.user)
            Budget.objects.create(
                user=request.user,
                category=category,
                amount=amount,
                start_date=start_date,
                end_date=end_date
            )
            messages.success(request, "Budget created successfully!")
            return redirect('budget')
        except Category.DoesNotExist:
            messages.error(request, "Selected category doesn't exist")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    categories = Category.objects.filter(user=request.user, category_type='expense')
    budgets = Budget.objects.filter(user=request.user).select_related('category')
    
    return render(request, 'budget.html', {
        'categories': categories,
        'budgets': budgets
    })


@login_required
def reports(request):
    # Monthly income and expenses - SQLite compatible version
    monthly_data = Transaction.objects.filter(user=request.user).extra(
        select={'month': "date(date, 'start of month')"}
    ).values('month', 'transaction_type').annotate(total=Sum('amount')).order_by('month')
    
    # Prepare monthly data for JSON serialization
    monthly_json_data = []
    for item in monthly_data:
        monthly_json_data.append({
            'month': item['month'],
            'transaction_type': item['transaction_type'],
            'total': float(item['total'])  # Convert Decimal to float for JSON
        })
    
    # Category-wise expenses
    expense_categories = Category.objects.filter(user=request.user, category_type='expense')
    category_data = []
    category_json_data = []
    for category in expense_categories:
        total = Transaction.objects.filter(
            user=request.user,
            category=category,
            transaction_type='expense'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        if total > 0:
            category_data.append({
                'name': category.name,
                'total': total,
                'color': category.color
            })
            category_json_data.append({
                'name': category.name,
                'total': float(total),  # Convert Decimal to float for JSON
                'color': category.color
            })
    
    context = {
        'monthly_data': monthly_data,
        'category_data': category_data,
        'monthly_json': json.dumps(monthly_json_data, cls=DjangoJSONEncoder),
        'category_json': json.dumps(category_json_data, cls=DjangoJSONEncoder),
    }
    return render(request, 'reports.html', context)

@login_required
def profile(request):
    user = request.user
    if request.method == 'POST':
        form = PasswordChangeForm(user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(user)
    return render(request, 'profile.html', {'user': user, 'form': form})