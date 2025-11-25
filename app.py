from flask import Flask, render_template, request, redirect, session
import json, os
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from openai import OpenAI

app = Flask(__name__, static_url_path='/static')
app.secret_key = "supersecretkey123"

USERS_FILE = "users.json"
DATA_FILE = "data.json"

# Load API key safely
def load_api_key():
    if os.path.exists("api_key.txt"):
        with open("api_key.txt", "r") as f:
            return f.read().strip()
    return None

# ============================
# JSON Load / Save
# ============================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"workspaces": {"Home": {"tasks": [], "notes": []}}, "current": "Home"}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_users():
    if not os.path.exists(USERS_FILE):
        return {"users": []}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ============================
# Login Required Decorator
# ============================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper

# ============================
# INDEX PAGE
# ============================
@app.route("/")
@login_required
def index():
    data = load_data()
    workspace = data["current"]

    # Auto-create missing workspace
    if workspace not in data["workspaces"]:
        data["workspaces"][workspace] = {"tasks": [], "notes": []}
        save_data(data)

    ws = data["workspaces"][workspace]
    now_date = date.today().isoformat()

    return render_template(
        "index.html",
        tasks=ws["tasks"],
        notes=ws["notes"],
        workspaces=data["workspaces"].keys(),
        current=workspace,
        now_date=now_date
    )

# ============================
# TASK FUNCTIONS
# ============================
@app.route("/add_task", methods=["POST"])
@login_required
def add_task():
    data = load_data()
    ws = data["workspaces"][data["current"]]
    priority = request.form.get("priority")


    ws["tasks"].append({
        "text": request.form.get("task"),
        "completed": False,
        "created": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
        "deadline": request.form.get("deadline") or None,
        "category": request.form.get("category") or None,
        "priority": priority if priority else "Low"
    })

    save_data(data)
    return redirect("/")

@app.route("/complete_task/<int:index>")
@login_required
def complete_task(index):
    data = load_data()
    ws = data["workspaces"][data["current"]]
    ws["tasks"][index]["completed"] ^= True
    save_data(data)
    return redirect("/")

@app.route("/delete_task/<int:index>")
@login_required
def delete_task(index):
    data = load_data()
    ws = data["workspaces"][data["current"]]
    ws["tasks"].pop(index)
    save_data(data)
    return redirect("/")

@app.route("/clear_completed")
@login_required
def clear_completed():
    data = load_data()
    ws = data["workspaces"][data["current"]]
    ws["tasks"] = [t for t in ws["tasks"] if not t["completed"]]
    save_data(data)
    return redirect("/")

@app.route("/edit_task/<int:index>", methods=["GET", "POST"])
@login_required
def edit_task(index):
    data = load_data()
    ws = data["workspaces"][data["current"]]

    if request.method == "POST":
        ws["tasks"][index]["text"] = request.form.get("task_text")
        save_data(data)
        return redirect("/")

    return render_template("edit_task.html", task_text=ws["tasks"][index]["text"], index=index)

# ============================
# NOTES
# ============================
@app.route("/add_note", methods=["POST"])
@login_required
def add_note():
    data = load_data()
    ws = data["workspaces"][data["current"]]
    note = request.form.get("note")
    if note.strip():
        ws["notes"].append(note)
    save_data(data)
    return redirect("/")

@app.route("/delete_note/<int:index>")
@login_required
def delete_note(index):
    data = load_data()
    ws = data["workspaces"][data["current"]]
    ws["notes"].pop(index)
    save_data(data)
    return redirect("/")

@app.route("/edit_note/<int:index>", methods=["GET", "POST"])
@login_required
def edit_note(index):
    data = load_data()
    ws = data["workspaces"][data["current"]]

    if request.method == "POST":
        ws["notes"][index] = request.form.get("note_text")
        save_data(data)
        return redirect("/")

    return render_template("edit_note.html", note_text=ws["notes"][index], index=index)

# ============================
# CALENDAR
# ============================
@app.route("/calendar")
@login_required
def calendar():
    data = load_data()
    ws = data["workspaces"][data["current"]]

    calendar_data = {}
    for t in ws["tasks"]:
        if t.get("deadline"):
            calendar_data.setdefault(t["deadline"], []).append(t)

    return render_template("calendar.html", calendar_data=calendar_data)

# ============================
# WORKSPACE MANAGEMENT
# ============================
@app.route("/switch/<name>")
@login_required
def switch(name):
    data = load_data()
    if name in data["workspaces"]:
        data["current"] = name
        save_data(data)
    return redirect("/")

@app.route("/create_workspace", methods=["POST"])
@login_required
def create_workspace():
    name = request.form.get("workspace")
    data = load_data()

    if name and name not in data["workspaces"]:
        data["workspaces"][name] = {"tasks": [], "notes": []}
        data["current"] = name
        save_data(data)

    return redirect("/")

@app.route("/delete_workspace/<name>", methods=["POST"])
@login_required
def delete_workspace(name):
    data = load_data()

    if len(data["workspaces"]) == 1:
        return redirect("/")  

    if name in data["workspaces"]:
        del data["workspaces"][name]

        if data["current"] == name:
            data["current"] = next(iter(data["workspaces"]))

        save_data(data)

    return redirect("/")

@app.route("/rename_workspace/<name>", methods=["POST"])
@login_required
def rename_workspace(name):
    data = load_data()
    new_name = request.form.get("new_name")

    if new_name and new_name not in data["workspaces"]:
        data["workspaces"][new_name] = data["workspaces"].pop(name)

        if data["current"] == name:
            data["current"] = new_name

        save_data(data)

    return redirect("/")

# ============================
# USER AUTH
# ============================
@app.route("/register", methods=["GET", "POST"])
def register():
    users = load_users()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if any(u["username"] == username for u in users["users"]):
            return "User already exists!"

        users["users"].append({
            "username": username,
            "password": generate_password_hash(password)
        })
        save_users(users)

        data = load_data()
        data["workspaces"][username] = {"tasks": [], "notes": []}
        save_data(data)

        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    users = load_users()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        for u in users["users"]:
            if u["username"] == username and check_password_hash(u["password"], password):
                session["user"] = username
                data = load_data()
                data["current"] = username

                if username not in data["workspaces"]:
                    data["workspaces"][username] = {"tasks": [], "notes": []}

                save_data(data)
                return redirect("/")

        return "Invalid username or password"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")

# ============================
# AI CHATBOT (AJAX)
# ============================
@app.route("/chat", methods=["POST"])
@login_required
def chat():
    user_msg = request.json.get("message")

    # Initialize chat history
    if "chat_history" not in session:
        session["chat_history"] = []

    session["chat_history"].append({
        "sender": "user",
        "text": user_msg,
        "time": datetime.now().strftime("%I:%M %p")
    })
    session.modified = True

    # AI TRY (ONLINE)
    try:
        client = OpenAI(api_key=load_api_key())
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful study planner assistant."},
                {"role": "user", "content": user_msg}
            ]
        )
        ai_reply = response.choices[0].message["content"]

    except:
        # OFFLINE fallback AI
        lower = user_msg.lower()
        if "timetable" in lower:
            ai_reply = "Study Plan:\n- 8-10 Math\n- 10-12 Physics\n- 2-4 Revision"
        elif "exam" in lower:
            ai_reply = "Exam Tip: Practice past papers and revise formulas daily."
        elif "plan" in lower:
            ai_reply = "Weekly Plan: Mon-Math, Tue-Physics, Wed-Chem, Thu-English, Fri-Revision."
        else:
            ai_reply = "Ask me for timetables, study plans, exam help, or productivity tips!"

    session["chat_history"].append({
        "sender": "ai",
        "text": ai_reply,
        "time": datetime.now().strftime("%I:%M %p")
    })
    session.modified = True

    return {"reply": ai_reply, "time": datetime.now().strftime("%I:%M %p")}

@app.route("/clear_chat", methods=["GET", "POST"])
@login_required
def clear_chat():
    session["chat_history"] = []
    session.modified = True
    return redirect("/")

# ============================
# RUN SERVER
# ============================
if __name__ == "__main__":
    app.run(debug=True)
