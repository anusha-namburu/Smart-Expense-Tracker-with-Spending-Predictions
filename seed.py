import os
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from app import create_app
from app.extensions import db
from app.models import User, Category, Transaction, Budget, SavingsGoal, RecurringExpense, Notification
from app.utils import init_default_categories, check_and_create_budget_alerts

def seed_demo_data():
    app = create_app('development')
    with app.app_context():
        # Ensure database tables and system default categories exist
        db.create_all()
        init_default_categories()

        demo_email = 'demo@smarttracker.com'
        demo_user = User.query.filter_by(email=demo_email).first()

        if demo_user:
            print(f"Removing existing demo data for {demo_email}...")
            # Clean existing demo records
            Transaction.query.filter_by(user_id=demo_user.id).delete()
            Budget.query.filter_by(user_id=demo_user.id).delete()
            SavingsGoal.query.filter_by(user_id=demo_user.id).delete()
            RecurringExpense.query.filter_by(user_id=demo_user.id).delete()
            Notification.query.filter_by(user_id=demo_user.id).delete()
            db.session.delete(demo_user)
            db.session.commit()

        print("Creating demo account: demo@smarttracker.com (Password: password123)...")
        demo_user = User(
            username="Alex Morgan",
            email=demo_email,
            currency="$"
        )
        demo_user.set_password("password123")
        db.session.add(demo_user)
        db.session.flush()

        # Query categories
        categories = {c.name: c for c in Category.query.all()}
        food_cat = categories.get('Food')
        transport_cat = categories.get('Transport')
        shopping_cat = categories.get('Shopping')
        bills_cat = categories.get('Bills')
        entertainment_cat = categories.get('Entertainment')
        health_cat = categories.get('Healthcare')
        housing_cat = categories.get('Housing')
        other_cat = categories.get('Other')

        salary_cat = categories.get('Salary')
        freelance_cat = categories.get('Freelancing')

        today = date.today()
        # Seed 120 days of historical transactions up to today
        start_date = today - timedelta(days=120)
        curr_d = start_date

        random.seed(42)  # Deterministic seed for reproducible testing & presentations

        created_tx_count = 0
        while curr_d <= today:
            # 1. Monthly Salary on 1st of each month
            if curr_d.day == 1 and salary_cat:
                salary_tx = Transaction(
                    user_id=demo_user.id,
                    category_id=salary_cat.id,
                    amount=Decimal('4800.00'),
                    type='income',
                    description="Monthly Tech Consulting Salary",
                    transaction_date=curr_d,
                    payment_method="Bank Transfer"
                )
                db.session.add(salary_tx)
                created_tx_count += 1

            # 2. Bi-weekly Freelancing Income on 15th of each month
            if curr_d.day == 15 and freelance_cat:
                fl_tx = Transaction(
                    user_id=demo_user.id,
                    category_id=freelance_cat.id,
                    amount=Decimal('750.00'),
                    type='income',
                    description="UI Design Contract Stipend",
                    transaction_date=curr_d,
                    payment_method="Direct Deposit"
                )
                db.session.add(fl_tx)
                created_tx_count += 1

            # 3. Monthly Rent / Housing on 2nd of each month
            if curr_d.day == 2 and housing_cat:
                rent_tx = Transaction(
                    user_id=demo_user.id,
                    category_id=housing_cat.id,
                    amount=Decimal('1200.00'),
                    type='expense',
                    description="Apartment Monthly Rent",
                    transaction_date=curr_d,
                    payment_method="Bank Transfer"
                )
                db.session.add(rent_tx)
                created_tx_count += 1

            # 4. Utilities and Internet on 10th
            if curr_d.day == 10 and bills_cat:
                bill_tx = Transaction(
                    user_id=demo_user.id,
                    category_id=bills_cat.id,
                    amount=Decimal('135.50'),
                    type='expense',
                    description="Electric & Water Utility Bill",
                    transaction_date=curr_d,
                    payment_method="Credit Card"
                )
                db.session.add(bill_tx)
                created_tx_count += 1

            # 5. Daily Food expenses (almost daily)
            if random.random() < 0.85 and food_cat:
                food_amt = round(random.uniform(14.50, 68.00), 2)
                descriptions = [
                    "Trader Joe's Groceries", "Whole Foods Market",
                    "Chipotle Lunch", "Starbucks Morning Coffee",
                    "Italian Bistro Dinner", "Local Bakery & Cafe"
                ]
                f_tx = Transaction(
                    user_id=demo_user.id,
                    category_id=food_cat.id,
                    amount=Decimal(str(food_amt)),
                    type='expense',
                    description=random.choice(descriptions),
                    transaction_date=curr_d,
                    payment_method=random.choice(["Credit Card", "Apple Pay", "Debit Card"])
                )
                db.session.add(f_tx)
                created_tx_count += 1

            # 6. Transport expenses (every 2-3 days)
            if random.random() < 0.45 and transport_cat:
                t_amt = round(random.uniform(12.00, 48.00), 2)
                t_desc = ["Shell Gas Station", "Metro Card Refill", "Uber Ride", "Chevron Fuel"]
                t_tx = Transaction(
                    user_id=demo_user.id,
                    category_id=transport_cat.id,
                    amount=Decimal(str(t_amt)),
                    type='expense',
                    description=random.choice(t_desc),
                    transaction_date=curr_d,
                    payment_method="Credit Card"
                )
                db.session.add(t_tx)
                created_tx_count += 1

            # 7. Shopping & Entertainment (predominantly weekends)
            is_weekend = curr_d.weekday() in [4, 5, 6]  # Fri, Sat, Sun
            if is_weekend and random.random() < 0.55:
                if random.random() < 0.5 and entertainment_cat:
                    ent_amt = round(random.uniform(22.00, 85.00), 2)
                    ent_desc = ["AMC Movie Tickets", "Concert Ticket", "Board Game Cafe", "Streaming Subscription"]
                    e_tx = Transaction(
                        user_id=demo_user.id,
                        category_id=entertainment_cat.id,
                        amount=Decimal(str(ent_amt)),
                        type='expense',
                        description=random.choice(ent_desc),
                        transaction_date=curr_d,
                        payment_method="Credit Card"
                    )
                    db.session.add(e_tx)
                    created_tx_count += 1
                elif shopping_cat:
                    shop_amt = round(random.uniform(35.00, 145.00), 2)
                    shop_desc = ["Amazon Basics Order", "Target Home Supplies", "Uniqlo Clothing", "Bookstore Purchase"]
                    s_tx = Transaction(
                        user_id=demo_user.id,
                        category_id=shopping_cat.id,
                        amount=Decimal(str(shop_amt)),
                        type='expense',
                        description=random.choice(shop_desc),
                        transaction_date=curr_d,
                        payment_method="Credit Card"
                    )
                    db.session.add(s_tx)
                    created_tx_count += 1

            curr_d += timedelta(days=1)

        print(f"Generated {created_tx_count} realistic synthetic transactions over 120 days.")

        # Seed Budgets for current month and previous month
        current_m = today.month
        current_y = today.year
        prev_m = 12 if current_m == 1 else current_m - 1
        prev_y = current_y - 1 if current_m == 1 else current_y

        # Overall monthly budget
        db.session.add(Budget(user_id=demo_user.id, category_id=None, monthly_limit=Decimal('2800.00'), month=current_m, year=current_y))
        db.session.add(Budget(user_id=demo_user.id, category_id=None, monthly_limit=Decimal('2800.00'), month=prev_m, year=prev_y))

        # Category budgets
        if food_cat:
            db.session.add(Budget(user_id=demo_user.id, category_id=food_cat.id, monthly_limit=Decimal('650.00'), month=current_m, year=current_y))
        if shopping_cat:
            db.session.add(Budget(user_id=demo_user.id, category_id=shopping_cat.id, monthly_limit=Decimal('350.00'), month=current_m, year=current_y))
        if transport_cat:
            db.session.add(Budget(user_id=demo_user.id, category_id=transport_cat.id, monthly_limit=Decimal('250.00'), month=current_m, year=current_y))
        if entertainment_cat:
            db.session.add(Budget(user_id=demo_user.id, category_id=entertainment_cat.id, monthly_limit=Decimal('200.00'), month=current_m, year=current_y))

        # Seed Savings Goals
        db.session.add(SavingsGoal(
            user_id=demo_user.id,
            title="Emergency Reserve Fund",
            target_amount=Decimal('8000.00'),
            current_amount=Decimal('5400.00'),
            target_date=today + timedelta(days=180),
            status='in_progress'
        ))
        db.session.add(SavingsGoal(
            user_id=demo_user.id,
            title="Tokyo Vacation Trip",
            target_amount=Decimal('3200.00'),
            current_amount=Decimal('1850.00'),
            target_date=today + timedelta(days=90),
            status='in_progress'
        ))
        db.session.add(SavingsGoal(
            user_id=demo_user.id,
            title="Ergonomic Workstation",
            target_amount=Decimal('950.00'),
            current_amount=Decimal('950.00'),
            target_date=today - timedelta(days=15),
            status='completed'
        ))

        # Seed Recurring Expense Templates
        if bills_cat:
            db.session.add(RecurringExpense(
                user_id=demo_user.id,
                category_id=bills_cat.id,
                amount=Decimal('79.99'),
                description="Fiber Gigabit Internet",
                payment_method="Credit Card",
                frequency='monthly',
                next_due_date=today + timedelta(days=8),
                is_active=True
            ))
        if entertainment_cat:
            db.session.add(RecurringExpense(
                user_id=demo_user.id,
                category_id=entertainment_cat.id,
                amount=Decimal('19.99'),
                description="4K Streaming Bundle",
                payment_method="Credit Card",
                frequency='monthly',
                next_due_date=today + timedelta(days=14),
                is_active=True
            ))

        # Seed in-app notifications
        db.session.add(Notification(
            user_id=demo_user.id,
            title="Welcome to Smart Expense Tracker!",
            message="Your account is set up with 120 days of historical expense data. Your Machine Learning prediction engine is trained and active.",
            type='info',
            is_read=True,
            dedup_key=f"welcome_{demo_user.id}"
        ))

        db.session.commit()

        # Run budget alert evaluation for demo user
        check_and_create_budget_alerts(demo_user.id, target_date=today)

        print("\n=======================================================")
        print(" Demo Data Successfully Seeded!")
        print("=======================================================")
        print(f" Login Email:    {demo_email}")
        print(f" Login Password: password123")
        print(f" History:        120 days of continuous data (~{created_tx_count} transactions)")
        print(f" ML Status:      Sufficient data available (RandomForestRegressor active)")
        print("=======================================================\n")

if __name__ == '__main__':
    seed_demo_data()
