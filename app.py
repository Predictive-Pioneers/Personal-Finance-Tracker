import pandas as pd
import os
from flask import Flask, render_template, request, redirect, url_for,session, send_file
import matplotlib
matplotlib.use("Agg") 
import matplotlib.pyplot as plt
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

CSV_PATH = os.path.join(DATA_DIR, "finance.csv")
USERS_FILE = os.path.join(DATA_DIR, "users.csv")

COLUMNS = ["id", "date", "time", "category", "type", "amount", "note"]
CATEGORIES = ["Salary", "Food", "Rent", "Travel", "Entertainment", "Shopping", "Bills", "Other"]
BUDGET_LIMITS = {
    "Food": 5000,
    "Rent": 15000,
    "Travel": 3000,
    "Entertainment": 2000,
    "Shopping": 4000,
    "Bills": 3000,
}
GOAL_COLUMNS = ["id", "name", "target_amount", "saved_amount"]

if not os.path.exists(CSV_PATH):
    df = pd.DataFrame(columns=COLUMNS)
    df.to_csv(CSV_PATH, index=False)
    print("New finance.csv created!")
else:
    df = pd.read_csv(CSV_PATH)
    if "time" not in df.columns:
        df["time"] = "00:00"   
        df.to_csv(CSV_PATH, index=False)
        print("Added 'time' column to existing data.")
    else:
        print("finance.csv already exists.")


if not os.path.exists(USERS_FILE):
    pd.DataFrame(columns=["username", "password_hash"]).to_csv(USERS_FILE, index=False)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def get_user_csv_path():
    username = session["username"]
    return os.path.join(DATA_DIR, f"finance_{username}.csv")


def ensure_user_csv_exists():
    path = get_user_csv_path()
    if not os.path.exists(path):
        pd.DataFrame(columns=COLUMNS).to_csv(path, index=False)

def generate_charts(df, username):
    expense_df = df[df["type"] == "Expense"]
    if not expense_df.empty:
        category_totals = expense_df.groupby("category")["amount"].sum()
        plt.figure(figsize=(5, 5))
        plt.pie(category_totals, labels=category_totals.index, autopct="%1.1f%%")
        plt.title("Expenses by Category")
        plt.savefig(os.path.join(STATIC_DIR, f"pie_chart_{username}.png"))
        plt.close()

    totals = df.groupby("type")["amount"].sum()
    plt.figure(figsize=(5, 4))
    totals.plot(kind="bar", color=["green", "red"])
    plt.title("Income vs Expense")
    plt.savefig(os.path.join(STATIC_DIR, f"bar_chart_{username}.png"))
    plt.close()


def check_budget_alerts(df):
    expense_df = df[df["type"] == "Expense"]
    category_totals = expense_df.groupby("category")["amount"].sum()

    alerts = []
    for category, limit in BUDGET_LIMITS.items():
        spent = category_totals.get(category, 0)
        if spent > limit:
            alerts.append({
                "category": category,
                "spent": spent,
                "limit": limit
            })
    return alerts

def get_user_categories_path():
    username = session["username"]
    return os.path.join(DATA_DIR, f"categories_{username}.json")

def get_user_categories():
    path = get_user_categories_path()
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)

def save_user_categories(categories):
    path = get_user_categories_path()
    with open(path, "w") as f:
        json.dump(categories, f)

def get_all_categories():
    return CATEGORIES + get_user_categories()

def get_user_goals_path():
    username = session["username"]
    return os.path.join(DATA_DIR, f"goals_{username}.csv")

def ensure_user_goals_exists():
    path = get_user_goals_path()
    if not os.path.exists(path):
        pd.DataFrame(columns=GOAL_COLUMNS).to_csv(path, index=False)

def get_available_months(df):
    if df.empty:
        return []
    months = df["date"].dt.strftime("%Y-%m").unique()
    months = sorted(months, reverse=True)
    result = []
    for m in months:
        display_name = pd.to_datetime(m).strftime("%B %Y")  # जैसे "July 2026"
        result.append({"value": m, "label": display_name})
    return result


app = Flask(__name__)
app.secret_key = "change-this-to-something-random-and-secret"


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        users_df = pd.read_csv(USERS_FILE)

        if username in users_df["username"].values:
            return render_template("signup.html", error="Username already taken!")

        new_user = {
            "username": username,
            "password_hash": generate_password_hash(password)
        }
        users_df = pd.concat([users_df, pd.DataFrame([new_user])], ignore_index=True)
        users_df.to_csv(USERS_FILE, index=False)

        session["username"] = username
        return redirect(url_for("dashboard"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        users_df = pd.read_csv(USERS_FILE)
        user_row = users_df[users_df["username"] == username]

        if user_row.empty or not check_password_hash(user_row.iloc[0]["password_hash"], password):
            return render_template("login.html", error="Invalid username or password")

        session["username"] = username
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    ensure_user_csv_exists()
    csv_path = get_user_csv_path()      
    df = pd.read_csv(csv_path)

    total_income = df[df["type"] == "Income"]["amount"].sum()
    total_expense = df[df["type"] == "Expense"]["amount"].sum()
    balance = total_income - total_expense

    return render_template("dashboard.html",
                            total_income=total_income,
                            total_expense=total_expense,
                            balance=balance)


@app.route("/add", methods=["GET"])
@login_required
def add_page():
    return render_template("add.html", categories=get_all_categories())


@app.route("/transactions")
@login_required
def transactions_page():
    ensure_user_csv_exists()
    csv_path = get_user_csv_path()      
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])

    available_months = get_available_months(df)

    selected_month = request.args.get("month", default="")
    search_query = request.args.get("search", default="").strip()

    if selected_month:
        df = df[df["date"].dt.strftime("%Y-%m") == selected_month]

    if search_query:
        mask = (
            df["category"].str.contains(search_query, case=False, na=False) |
            df["type"].str.contains(search_query, case=False, na=False) |
            df["note"].str.contains(search_query, case=False, na=False)
        )
        df = df[mask]

    transactions = df.to_dict(orient="records")

    return render_template("transactions.html", transactions=transactions,
                            selected_month=selected_month, search_query=search_query,
                            available_months=available_months)


@app.route("/charts")
@login_required
def charts_page():
    ensure_user_csv_exists()
    csv_path = get_user_csv_path()
    df = pd.read_csv(csv_path)
    generate_charts(df, session["username"])
    return render_template("charts.html", username=session["username"])


@app.route("/budget")
@login_required
def budget_page():
    ensure_user_csv_exists()
    csv_path = get_user_csv_path()      
    df = pd.read_csv(csv_path)
    alerts = check_budget_alerts(df)

    expense_df = df[df["type"] == "Expense"]
    category_totals = expense_df.groupby("category")["amount"].sum()

    budget_status = []
    for category, limit in BUDGET_LIMITS.items():
        spent = category_totals.get(category, 0)
        budget_status.append({
            "category": category,
            "spent": spent,
            "limit": limit
        })

    return render_template("budget.html", alerts=alerts, budget_status=budget_status)


@app.route("/add", methods=["POST"])
@login_required
def add_transaction():
    ensure_user_csv_exists()
    csv_path = get_user_csv_path()      
    df = pd.read_csv(csv_path)

    new_id = int(df["id"].max()) + 1 if not df.empty else 1

    new_row = {
        "id": new_id,
        "date": request.form["date"],
        "time": request.form["time"],
        "category": request.form["category"],
        "type": request.form["type"],
        "amount": float(request.form["amount"]),
        "note": request.form["note"]
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(csv_path, index=False)

    return redirect(url_for("transactions_page"))


@app.route("/delete/<int:txn_id>")
@login_required
def delete_transaction(txn_id):
    ensure_user_csv_exists()
    csv_path = get_user_csv_path()      
    df = pd.read_csv(csv_path)
    df = df[df["id"] != txn_id]
    df.to_csv(csv_path, index=False)
    return redirect(url_for("transactions_page"))


@app.route("/edit/<int:txn_id>")
@login_required
def edit_transaction(txn_id):
    ensure_user_csv_exists()
    csv_path = get_user_csv_path()      
    df = pd.read_csv(csv_path)
    transaction = df[df["id"] == txn_id].to_dict(orient="records")[0]
    return render_template("edit.html", transaction=transaction, categories=get_all_categories())


@app.route("/update/<int:txn_id>", methods=["POST"])
@login_required
def update_transaction(txn_id):
    ensure_user_csv_exists()
    csv_path = get_user_csv_path()      
    df = pd.read_csv(csv_path)

    df.loc[df["id"] == txn_id, "date"] = request.form["date"]
    df.loc[df["id"] == txn_id, "time"] = request.form["time"]
    df.loc[df["id"] == txn_id, "category"] = request.form["category"]
    df.loc[df["id"] == txn_id, "type"] = request.form["type"]
    df.loc[df["id"] == txn_id, "amount"] = float(request.form["amount"])
    df.loc[df["id"] == txn_id, "note"] = request.form["note"]

    df.to_csv(csv_path, index=False)
    return redirect(url_for("transactions_page"))


@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories_page():
    if request.method == "POST":
        new_cat = request.form["category"].strip()
        custom_categories = get_user_categories()
        if new_cat and new_cat not in CATEGORIES and new_cat not in custom_categories:
            custom_categories.append(new_cat)
            save_user_categories(custom_categories)
        return redirect(url_for("categories_page"))

    return render_template("categories.html",
                            built_in=CATEGORIES,
                            custom=get_user_categories())


@app.route("/categories/delete/<category_name>")
@login_required
def delete_category(category_name):
    custom_categories = get_user_categories()
    if category_name in custom_categories:
        custom_categories.remove(category_name)
        save_user_categories(custom_categories)
    return redirect(url_for("categories_page"))


@app.route("/goals")
@login_required
def goals_page():
    ensure_user_goals_exists()
    goals_path = get_user_goals_path()
    df = pd.read_csv(goals_path)
    goals = df.to_dict(orient="records")
    return render_template("goals.html", goals=goals)


@app.route("/goals/add", methods=["POST"])
@login_required
def add_goal():
    ensure_user_goals_exists()
    goals_path = get_user_goals_path()
    df = pd.read_csv(goals_path)

    new_id = int(df["id"].max()) + 1 if not df.empty else 1

    new_goal = {
        "id": new_id,
        "name": request.form["name"],
        "target_amount": float(request.form["target_amount"]),
        "saved_amount": 0.0
    }

    df = pd.concat([df, pd.DataFrame([new_goal])], ignore_index=True)
    df.to_csv(goals_path, index=False)

    return redirect(url_for("goals_page"))


@app.route("/goals/contribute/<int:goal_id>", methods=["POST"])
@login_required
def contribute_goal(goal_id):
    ensure_user_goals_exists()
    goals_path = get_user_goals_path()
    df = pd.read_csv(goals_path)

    amount = float(request.form["amount"])
    df.loc[df["id"] == goal_id, "saved_amount"] += amount

    df.to_csv(goals_path, index=False)
    return redirect(url_for("goals_page"))


@app.route("/goals/delete/<int:goal_id>")
@login_required
def delete_goal(goal_id):
    ensure_user_goals_exists()
    goals_path = get_user_goals_path()
    df = pd.read_csv(goals_path)
    df = df[df["id"] != goal_id]
    df.to_csv(goals_path, index=False)
    return redirect(url_for("goals_page"))

@app.route("/download")
@login_required
def download_data():
    ensure_user_csv_exists()
    csv_path = get_user_csv_path()
    username = session["username"]

    return send_file(csv_path,
                      as_attachment=True,
                      download_name=f"finance_data_{username}.csv")


if __name__ == "__main__":
    app.run(debug=False)