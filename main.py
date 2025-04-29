import os
from flask import *
import sqlite3
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import smtplib
app = Flask(__name__)
app.secret_key = "secret key"
def connect():
	return sqlite3.connect("tasify.db")

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'txt'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'id' not in session:
        return redirect('/login')

    conn = connect()
    cursor = conn.cursor()

    # Fetch all users except the current logged-in user
    cursor.execute("SELECT uid, username FROM users WHERE uid != ?", (session["id"],))
    u = cursor.fetchall()

    users = []
    for k in u:
        k = list(k)  # Convert tuple to list to append unread message count
        cursor.execute("""
            SELECT count(*)
            FROM accounts_chat 
            WHERE to_user_id = ? AND reads = 0 and from_user_id=?
            ORDER BY trans ASC
        """, ( session["id"],k[0]))
        c = cursor.fetchone()[0]
        k.append(c)
        users.append(k)

    selected_user = None
    messages = []

    # Handle GET request when a specific user is selected
    if request.method == "GET" and "user_id" in request.args:
        selected_user_id = request.args.get("user_id")
        cursor.execute("SELECT uid, username FROM users WHERE uid = ?", (selected_user_id,))
        selected_user = cursor.fetchone()
        print(selected_user)

        if selected_user:
            # Mark messages as read
            cursor.execute("""
                UPDATE accounts_chat
                SET reads = 1
                WHERE from_user_id = ? AND to_user_id = ? AND reads = 0
            """, (selected_user_id, session["id"]))
            conn.commit()

            # Fetch chat messages between the users
            cursor.execute("""
                SELECT from_user_id, text, trans, reads, file, cid
                FROM accounts_chat 
                WHERE (from_user_id = ? AND to_user_id = ?) OR (from_user_id = ? AND to_user_id = ?) 
                ORDER BY trans ASC
            """, (session["id"], selected_user_id, selected_user_id, session["id"]))
            messages = cursor.fetchall()

    # Handle POST request for sending a message
    if request.method == "POST":
        text = request.form["message"]
        to_user = request.form["to_user"]
        file = request.files.get("file")
        filename = None

        # If a file is uploaded, save it
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

        # Insert the new chat message into the database
        cursor.execute("""
            INSERT INTO accounts_chat (text, trans, from_user_id, to_user_id, file, reads)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (text, datetime.now(), session["id"], to_user, filename, 0))
        conn.commit()

        return redirect(f'/chat?user_id={to_user}')

    conn.close()
    return render_template("chat.html", users=users, selected_user=selected_user, messages=messages)

@app.route('/delete_message', methods=['POST'])
def delete_message():
    if 'id' not in session:
        return redirect('/login')

    cid = request.form.get("cid")
    print(cid)  # Corrected indentation

    conn = connect()
    cursor = conn.cursor()

    # Check ownership before deleting
    cursor.execute("SELECT file FROM accounts_chat WHERE cid = ? AND from_user_id = ?", (cid, session['id']))
    row = cursor.fetchone()
    if row:
        file_path = row[0]
        # Delete associated file from storage
        if file_path:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], file_path)
            if os.path.exists(full_path):
                os.remove(full_path)
        cursor.execute("DELETE FROM accounts_chat WHERE cid = ?", (cid,))
        conn.commit()

    conn.close()
    return redirect(request.referrer)
@app.route('/', methods=['POST', 'GET'])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = connect()
        cursor = conn.cursor()

        # Check in admin table
        cursor.execute("SELECT * FROM admin WHERE adminname=? AND adminpassword=?", (username, password))
        user = cursor.fetchone()

        if user:
            session["id"] = user[0]
            session["username"] = username
            session["role"] = "admin"
            cursor.close()
            conn.close()
            return redirect("/dashboard")

        # Check in users table
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()

        if user:
            session["id"] = user[0]
            session["username"] = username
            session["role"] = "user"

            # Get unread chat count
            user_id = user[0]
            cursor.execute("SELECT COUNT(*) FROM accounts_chat WHERE to_user_id=? AND reads=0", (user_id,))
            chat_count = cursor.fetchone()[0]
            session["chat_count"] = chat_count  # optional: for displaying in navbar or dashboard

            cursor.close()
            conn.close()
            return redirect("/dashboard")

        cursor.close()
        conn.close()
        return "Invalid credentials! Please try again.", 401

    return render_template('login.html')
@app.route('/register', methods=['POST'])
def insertusers():
	# Extract data from the form
	password = request.form['password']
	last_login = ""
	username = request.form['username']
	email = request.form['email']
	is_staff = 0
	date_joined = ""
	isapproved = 0
	
	# Connect to SQLite database (or create it if it doesn't exist)
	conn = connect()
	cursor = conn.cursor()
	try:
		cursor.execute('select uid from users order by uid desc limit 1')
		uid=cursor.fetchone()[0]+1
	except:
		uid=1
	
	# Insert data into the users table
	try:
		cursor.execute('''INSERT INTO users (uid,password,last_login,username,email,is_staff,date_joined,isapproved)values(?,?,?,?,?,?,?,?)''',(uid,password,last_login,username,email,is_staff,date_joined,isapproved))
		# Commit the transaction
		conn.commit()
		cursor.close()
		conn.close()

		return redirect("/")
	except Exception as e:
		return jsonify({'error': str(e)}), 400
	

@app.route('/dashboard')
def dashboard():
    if "role" not in session:
        return redirect('/')

    conn = connect()
    cursor = conn.cursor()

    notification_count = 0
    if session['role'] == 'user':
        cursor.execute("SELECT COUNT(*) FROM accounts_chat WHERE to_user_id=? AND reads=0", (session['id'],))
        notification_count = cursor.fetchone()[0]

    # Handle performance analysis range filter
    range_filter = request.args.get("range", "week")  # default is week
    today = datetime.today().date()

    if range_filter == "week":
        start_date = today - timedelta(days=6)
    elif range_filter == "month":
        start_date = today - timedelta(days=29)
    elif range_filter == "year":
        start_date = today - timedelta(days=364)
    else:
        start_date = today - timedelta(days=6)

    # Get task count grouped by day
    cursor.execute("""
        SELECT DATE(end_date) as task_date, COUNT(*) as count
        FROM task
        WHERE end_date BETWEEN ? AND ?
        GROUP BY DATE(end_date)
        ORDER BY task_date ASC
    """, (start_date, today))
    task_data = cursor.fetchall()

    task_dates = [row[0] for row in task_data]
    task_counts = [row[1] for row in task_data]

    if session["role"] == "admin":
        # Admin dashboard stats
        cursor.execute("SELECT COUNT(*) FROM task")
        total_tasks = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM task WHERE end_date = ?", (today,))
        today_tasks = cursor.fetchone()[0]

        three_days_from_now = today + timedelta(days=3)
        cursor.execute("SELECT COUNT(*) FROM task WHERE end_date BETWEEN ? AND ?", (today, three_days_from_now))
        three_day_tasks = cursor.fetchone()[0]

        # Overdue tasks query
        cursor.execute("SELECT COUNT(*) FROM task WHERE end_date < ? AND status != 'completed'", (today,))
        overdue_tasks = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM accounts_task_assigned_to WHERE groupid IS NULL")
        personal_tasks = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM accounts_task_assigned_to WHERE groupid IS NOT NULL")
        group_tasks = cursor.fetchone()[0]

        # 🆕 Add total users count
        cursor.execute("SELECT COUNT(*) FROM users")  # Adjust if your user table is named differently
        total_users = cursor.fetchone()[0]
        

        conn.close()

        return render_template(
            "dashboard.html",
            
            total_tasks=total_tasks,
            today_tasks=today_tasks,
            three_day_tasks=three_day_tasks,
            overdue_tasks=overdue_tasks,  # Pass overdue tasks to the template
            personal_tasks=personal_tasks,
            group_tasks=group_tasks,
            total_users=total_users,
            task_dates=task_dates,
            task_counts=task_counts,
            selected_range=range_filter,
            notification_count=notification_count
        )

    elif session["role"] == "user":
        user_id = session['id']

        cursor.execute("SELECT COUNT(*) FROM accounts_task_assigned_to WHERE user_id=? AND groupid IS NULL", (user_id,))
        personal_tasks = cursor.fetchone()[0]

        cursor.execute("select count(*) from task t join  accounts_task_assigned_to a on t.id=a.task_id join group_member gm on gm.gid=a.groupid where  a.groupid IS not NULL and uid='%s';"% (user_id,))
        group_tasks = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM  task t JOIN accounts_task_assigned_to a ON t.id = a.task_id  WHERE user_id=? AND groupid IS NULL AND DATE(reminder)=?", (user_id, today))
        personal_tasks_rem = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM task t 
            JOIN accounts_task_assigned_to a ON t.id = a.task_id 
            JOIN group_member gm ON gm.gid = a.groupid 
            WHERE a.groupid IS NOT NULL AND gm.uid = ? AND DATE(reminder)=?
        """, (user_id, today))
        group_tasks_rem = cursor.fetchone()[0]

        today_reminders = personal_tasks_rem + group_tasks_rem
        conn.close()

        return render_template(
            "dashboard.html",
            today_reminders=today_reminders,
            personal_tasks=personal_tasks,
            group_tasks=group_tasks,
            task_dates=task_dates,
            task_counts=task_counts,
            selected_range=range_filter,
            notification_count=notification_count
        )


@app.route('/managetask')
def managetask():
    conn = connect()
    cursor = conn.cursor()
    uid = session["id"]
    # Fetch only personal tasks assigned to the logged-in user
    cursor.execute("""
        SELECT t.id, t.task_name, t.description, t.priority, t.reminder, 
            t.created_at, t.end_date, t.start_date, u.username, t.status, u.username,
             t.created_by_id       
        FROM task t 
        JOIN accounts_task_assigned_to ata ON t.id = ata.task_id
        JOIN users u ON ata.user_id = u.uid
        WHERE ata.user_id = ?
    """, (uid,))
    personal_tasks = cursor.fetchall()

    # Fetch only group tasks where the user is part of the group
    cursor.execute("""
        SELECT t.id, t.task_name, t.description, t.priority, t.reminder, 
            t.created_at, t.end_date, t.start_date, u.username, t.status, g.groupname ,t.created_by_id
        FROM task t 
        JOIN accounts_task_assigned_to ata ON t.id = ata.task_id
        JOIN groupsdetails g ON ata.groupid = g.gid join group_member gm on gm.gid=g.gid join
        users u on u.uid=gm.uid
        WHERE ata.groupid IN (SELECT groupid FROM accounts_task_assigned_to WHERE groupid in (select gid from group_member where uid=? ))
    """, (uid,))
    group_tasks = cursor.fetchall()
    conn.close()
    return render_template(
        'managetask.html',
        personal_tasks=personal_tasks,
        group_tasks=group_tasks,
        columns=['id', 'task_name', 'description', 'priority', 'reminder', 'created_at', 'end_date', 'start_date', 'created_by_id', 'status', 'assigned_to']
    )
@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    conn = connect()
    cursor = conn.cursor()

    if request.method == 'POST':
        task_name = request.form['task_name']
        description = request.form['description']
        priority = request.form['priority']
        reminder = request.form.get('reminder') == 'on'
        start_date = request.form['start_date']
        end_date = request.form['end_date']

        cursor.execute('''
            UPDATE task SET task_name = ?, description = ?, priority = ?, reminder = ?, 
            start_date = ?, end_date = ? WHERE id = ?
        ''', (task_name, description, priority, reminder, start_date, end_date, task_id))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))  # Update this to your dashboard route
    else:
        cursor.execute('SELECT * FROM task WHERE id = ?', (task_id,))
        task = cursor.fetchone()
        conn.close()
        return render_template('edit_task.html', task=task)
@app.route('/total_tasks')
def total_tasks():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""SELECT 
    t.id,
    t.task_name,
    t.description,
    t.priority,
	t.start_date,
    t.created_at,
    t.end_date,
    
    t.status,
    COALESCE(u.username, g.groupname) AS assigned_to
FROM 
    task t
JOIN 
    accounts_task_assigned_to a ON t.id = a.task_id
LEFT JOIN 
    users u ON a.user_id = u.uid
LEFT JOIN 
    groupsdetails g ON a.groupid = g.gid;""")
    tasks = cursor.fetchall()
    conn.close()
    return render_template("task_list.html", title="Total Tasks", tasks=tasks)
@app.route('/today_tasks')
def today_tasks():
    conn = connect()
    cursor = conn.cursor()
    today = datetime.today().date()

    cursor.execute("""
        SELECT 
            t.id,
            t.task_name,
            t.description,
            t.priority,
            t.start_date,
            t.created_at,
            t.end_date,
            t.status,
            COALESCE(u.username, g.groupname) AS assigned_to
        FROM 
            task t
        JOIN 
            accounts_task_assigned_to a ON t.id = a.task_id
        LEFT JOIN 
            users u ON a.user_id = u.uid
        LEFT JOIN 
            groupsdetails g ON a.groupid = g.gid
        WHERE 
            t.end_date = ?
    """, (today,))

    tasks = cursor.fetchall()
    conn.close()
    return render_template("task_list.html", title="Today's Tasks", tasks=tasks)


@app.route('/due_tasks')
def due_tasks():
    conn = connect()
    cursor = conn.cursor()
    today = datetime.today().date()
    three_days = today + timedelta(days=3)

    cursor.execute("""
        SELECT 
            t.id,
            t.task_name,
            t.description,
            t.priority,
            t.start_date,
            t.created_at,
            t.end_date,
            t.status,
            COALESCE(u.username, g.groupname) AS assigned_to
        FROM 
            task t
        JOIN 
            accounts_task_assigned_to a ON t.id = a.task_id
        LEFT JOIN 
            users u ON a.user_id = u.uid
        LEFT JOIN 
            groupsdetails g ON a.groupid = g.gid
        WHERE 
            t.end_date BETWEEN ? AND ?
    """, (today, three_days))

    tasks = cursor.fetchall()
    conn.close()
    return render_template("task_list.html", title="Tasks Due in 3 Days", tasks=tasks)

@app.route('/overdue_tasks')
def overdue_tasks():
    conn = connect()
    cursor = conn.cursor()
    today = datetime.today().date()

    cursor.execute("""
        SELECT 
            t.id,
            t.task_name,
            t.description,
            t.priority,
            t.start_date,
            t.created_at,
            t.end_date,
            t.status,
            COALESCE(u.username, g.groupname) AS assigned_to
        FROM 
            task t
        JOIN 
            accounts_task_assigned_to a ON t.id = a.task_id
        LEFT JOIN 
            users u ON a.user_id = u.uid
        LEFT JOIN 
            groupsdetails g ON a.groupid = g.gid
        WHERE 
            t.end_date < ? AND status != 'completed'
    """, (today, ))

    tasks = cursor.fetchall()
    conn.close()
    return render_template("task_list.html", title="Overdue Task", tasks=tasks)


@app.route('/personal_tasks')
def personal_tasks():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""SELECT 
    t.id,
    t.task_name,
    t.description,
    t.priority,
	t.start_date,
    t.created_at,
    t.end_date,
    
    t.status,
    COALESCE(u.username, g.groupname) AS assigned_to
FROM 
    task t
JOIN 
    accounts_task_assigned_to a ON t.id = a.task_id
LEFT JOIN 
    users u ON a.user_id = u.uid
LEFT JOIN 
    groupsdetails g ON a.groupid = g.gid  WHERE a.groupid IS NULL""")
    tasks = cursor.fetchall()
    conn.close()
    return render_template("task_list.html", title="Personal Tasks", tasks=tasks)

@app.route('/todaypersonal_tasks')
def todaypersonal_tasks():
    if 'id' not in session:
        return redirect('/')

    conn = connect()
    cursor = conn.cursor()
    
    today = datetime.today().date()
    user_id = session['id']

    cursor.execute("""
        SELECT 
            t.id,
            t.task_name,
            t.description,
            t.priority,
            t.start_date,
            t.created_at,
            t.end_date,
            t.status,
            COALESCE(u.username, g.groupname) AS assigned_to
        FROM 
            task t
        JOIN 
            accounts_task_assigned_to a ON t.id = a.task_id
        LEFT JOIN 
            users u ON a.user_id = u.uid
        LEFT JOIN 
            groupsdetails g ON a.groupid = g.gid  
        WHERE 
            a.groupid IS NULL 
            AND a.user_id = ? 
            AND DATE(t.start_date) = ?
    """, (user_id, today))
    
    tasks = cursor.fetchall()
    conn.close()
    return render_template("task_list.html", title="Today's Personal Tasks", tasks=tasks)
@app.route("/chart")
def chart():
    db = connect()
    db.row_factory = sqlite3.Row
    

    time_filter = request.args.get("time", "all")
    
    def get_date_filter_clause(column):
        today = datetime.today()
        if time_filter == "today":
            return f"AND date({column}) = date('now')"
        elif time_filter == "this_week":
            return f"AND strftime('%W', {column}) = strftime('%W', 'now') AND strftime('%Y', {column}) = strftime('%Y', 'now')"
        elif time_filter == "this_month":
            return f"AND strftime('%m', {column}) = strftime('%m', 'now') AND strftime('%Y', {column}) = strftime('%Y', 'now')"
        elif time_filter == "last_month":
            return f"AND strftime('%m', {column}) = strftime('%m', 'now', '-1 month') AND strftime('%Y', {column}) = strftime('%Y', 'now', '-1 month')"
        return ""  # all

    date_clause = get_date_filter_clause("t.end_date")
    user_data = []
    group_data = []

    if session["role"] == "admin":
        # User-level stats
        users = db.execute("SELECT uid, username FROM users").fetchall()

        for user in users:
            uid = user["uid"]
            name = user["username"]

            total = db.execute("""
                SELECT COUNT(*) FROM task t 
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                WHERE a.user_id = ? 
            """+ date_clause, (uid,)).fetchone()[0]

            ontime = db.execute("""
                SELECT COUNT(*) FROM task t 
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                WHERE a.user_id = ? AND t.status = 'completed' AND date(t.end_date) >= date(t.reminder)
            """+ date_clause, (uid,)).fetchone()[0]

            overdue = db.execute("""
                SELECT COUNT(*) FROM task t 
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                WHERE a.user_id = ? AND t.status != 'completed' AND date(t.end_date) < date('now')
            """+ date_clause, (uid,)).fetchone()[0]

            pending = db.execute("""
                SELECT COUNT(*) FROM task t 
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                WHERE a.user_id = ? AND t.status = 'Assigned'
            """+ date_clause, (uid,)).fetchone()[0]

            user_data.append({
                "name": name,
                "ontime": ontime,
                "overdue": overdue,
                "pending": pending,
                "total": total
            })

        # Group-level stats
        groups = db.execute("SELECT gid, groupname FROM groupsdetails").fetchall()

        for group in groups:
            gid = group["gid"]
            groupname = group["groupname"]

            total = db.execute("""
                SELECT COUNT(*) FROM task t
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                WHERE a.groupid = ?
            """+ date_clause, (gid,)).fetchone()[0]

            ontime = db.execute("""
                SELECT COUNT(*) FROM task t
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                WHERE a.groupid = ? AND t.status = 'completed' AND date(t.end_date) >= date(t.reminder)
            """+ date_clause, (gid,)).fetchone()[0]

            overdue = db.execute("""
                SELECT COUNT(*) FROM task t
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                WHERE a.groupid = ? AND t.status != 'completed' AND date(t.end_date) < date('now')
            """+ date_clause, (gid,)).fetchone()[0]

            pending = db.execute("""
                SELECT COUNT(*) FROM task t
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                WHERE a.groupid = ? AND t.status = 'Assigned'
            """+ date_clause, (gid,)).fetchone()[0]

            group_data.append({
                "groupname": groupname,
                "ontime": ontime,
                "overdue": overdue,
                "pending": pending,
                "total": total
            })

        print("User data:", user_data)
        print("Group data:", group_data)

    elif session["role"] == "user":
        uid = session["id"]
        name = db.execute("SELECT username FROM users WHERE uid = ?", (uid,)).fetchone()["username"]

        total = db.execute("""
            SELECT COUNT(*) FROM task t 
            JOIN accounts_task_assigned_to a ON t.id = a.task_id 
            WHERE a.user_id = ?
        """+ date_clause, (uid,)).fetchone()[0]

        ontime = db.execute("""
            SELECT COUNT(*) FROM task t 
            JOIN accounts_task_assigned_to a ON t.id = a.task_id 
            WHERE a.user_id = ? AND t.status = 'completed' AND date(t.end_date) >= date(t.reminder)
        """+ date_clause, (uid,)).fetchone()[0]

        overdue = db.execute("""
            SELECT COUNT(*) FROM task t 
            JOIN accounts_task_assigned_to a ON t.id = a.task_id 
            WHERE a.user_id = ? AND t.status != 'completed' AND date(t.end_date) < date('now')
        """+ date_clause, (uid,)).fetchone()[0]

        pending = db.execute("""
            SELECT COUNT(*) FROM task t 
            JOIN accounts_task_assigned_to a ON t.id = a.task_id 
            WHERE a.user_id = ? AND t.status = 'Assigned'
        """+ date_clause, (uid,)).fetchone()[0]

        user_data.append({
            "name": name,
            "ontime": ontime,
            "overdue": overdue,
            "pending": pending,
            "total": total
        })

        print("Logged-in user data:", user_data)
        groups = db.execute("SELECT gid, groupname FROM groupsdetails").fetchall()
        group_data = []

        for group in groups:
            gid = group["gid"]
            groupname = group["groupname"]

            total = db.execute("""
                SELECT COUNT(*) FROM task t
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                join group_member g on a.groupid=g.gid
                WHERE a.groupid = ? and g.uid=?
            """+ date_clause, (gid,uid)).fetchone()[0]

            ontime = db.execute("""
                SELECT COUNT(*) FROM task t
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                join group_member g on a.groupid=g.gid
                WHERE a.groupid = ? and g.uid=? AND t.status = 'completed' AND date(t.end_date) >= date(t.reminder)
            """+ date_clause, (gid,uid)).fetchone()[0]

            overdue = db.execute("""
                SELECT COUNT(*) FROM task t
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                 join group_member g on a.groupid=g.gid
                WHERE a.groupid = ? and g.uid=? AND t.status != 'completed' AND date(t.end_date) < date('now')
            """+ date_clause, (gid,uid)).fetchone()[0]

            pending = db.execute("""
                SELECT COUNT(*) FROM task t
                JOIN accounts_task_assigned_to a ON t.id = a.task_id 
                join group_member g on a.groupid=g.gid
                WHERE a.groupid = ? and g.uid=? AND t.status = 'Assigned'
            """+ date_clause, (gid,uid)).fetchone()[0]

            group_data.append({
                "groupname": groupname,
                "ontime": ontime,
                "overdue": overdue,
                "pending": pending,
                "total": total
            })

    return render_template("admin_dashboard.html", user_data=user_data, group_data=group_data)



@app.route('/group_tasks')
def group_tasks():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""SELECT 
    t.id,
    t.task_name,
    t.description,
    t.priority,
	t.start_date,
    t.created_at,
    t.end_date,
    
    t.status,
    COALESCE(u.username, g.groupname) AS assigned_to
FROM 
    task t
JOIN 
    accounts_task_assigned_to a ON t.id = a.task_id
LEFT JOIN 
    users u ON a.user_id = u.uid
LEFT JOIN 
    groupsdetails g ON a.groupid = g.gid  WHERE a.groupid IS not NULL""")
    tasks = cursor.fetchall()
    conn.close()
    return render_template("task_list.html", title="Group Tasks", tasks=tasks)

@app.route('/personal_tasksuser')
def personal_tasksuser():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""SELECT 
    t.id,
    t.task_name,
    t.description,
    t.priority,
	t.start_date,
    t.created_at,
    t.end_date,
    
    t.status,
    COALESCE(u.username, g.groupname) AS assigned_to
FROM 
    task t
JOIN 
    accounts_task_assigned_to a ON t.id = a.task_id
LEFT JOIN 
    users u ON a.user_id = u.uid
LEFT JOIN 
    groupsdetails g ON a.groupid = g.gid  WHERE a.groupid IS NULL and u.uid='%s'"""%(session["id"]))
    tasks = cursor.fetchall()
    conn.close()
    return render_template("task_list.html", title="Personal Tasks", tasks=tasks)

@app.route('/group_tasksuser')
def group_tasksuser():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""SELECT 
    t.id,
    t.task_name,
    t.description,
    t.priority,
	t.start_date,
    t.created_at,
    t.end_date,
    t.status,
    COALESCE(u.username, g.groupname) AS assigned_to,
    u.uid
FROM 
    task t
JOIN 
    accounts_task_assigned_to a ON t.id = a.task_id
LEFT JOIN 
    groupsdetails g ON a.groupid = g.gid LEFT JOIN 
    group_member gm on gm.gid=g.gid left join 
    users u ON gm.uid = u.uid WHERE a.groupid IS not NULL and u.uid='%s' """%(session["id"]))
    tasks = cursor.fetchall()
    conn.close()
    return render_template("task_list.html", title="Group Tasks", tasks=tasks)

@app.route('/inserttask1')
def inserttask1():
	conn = connect()
	cursor = conn.cursor()
	cursor.execute("select * from users where is_staff=0")
	user=cursor.fetchall()
	conn = connect()
	cursor = conn.cursor()
	cursor.execute("select * from groupsdetails")
	group=cursor.fetchall()
	return render_template('inserttask.html',user=user,group=group)
def sendmail(r, msg):
    try:
        mail = smtplib.SMTP('smtp.gmail.com', 587)
        mail.ehlo()
        mail.starttls()
        mail.login('classvebbox@gmail.com', 'wfvmiraatzkeqncw')  # App password
        mail.sendmail('classvebbox@gmail.com', r, msg)
        print("Mail sent successfully.")
    except Exception as e:
        print("Error sending mail:", str(e))

@app.route('/inserttask', methods=['POST'])
def inserttask():
    task_name = request.form['task_name']
    description = request.form['description']
    priority = request.form['priority']
    reminder = request.form['reminder']
    end_date = request.form['end_date']
    start_date = request.form['start_date']
    created_by_name = request.form['created_by_id']
    created_by_id = session["id"]
    status = "Assigned"
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    assign_to = request.form['assign_to']
    assign_to_gr = request.form['assign_to_group']
    assign = "user" if assign_to_gr == 'Select group' else "group"

    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT id FROM task ORDER BY id DESC LIMIT 1')
        tid = cursor.fetchone()[0] + 1
    except:
        tid = 1

    try:
        cursor.execute('''INSERT INTO task (id, task_name, description, priority, reminder, created_at, end_date, start_date, created_by_id, status)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (tid, task_name, description, priority, reminder, created_at, end_date, start_date, created_by_id, status))
        conn.commit()

        cursor.close()
        conn.close()

        # Open new connection for task assignment
        conn = connect()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT id FROM accounts_task_assigned_to ORDER BY id DESC LIMIT 1')
            id = cursor.fetchone()[0] + 1
        except:
            id = 1

        # Assign task to user or group
        if assign == "user":
            cursor.execute("SELECT email FROM users WHERE uid = ?", (assign_to,))
            user_email = cursor.fetchone()[0]

            cursor.execute('''INSERT INTO accounts_task_assigned_to (id, task_id, user_id)
                              VALUES (?, ?, ?)''', (id, tid, assign_to))
        else:
            cursor.execute("SELECT email FROM users WHERE uid IN (SELECT uid FROM group_member WHERE gid = ?)", (assign_to_gr,))
            group_emails = [row[0] for row in cursor.fetchall()]

            cursor.execute('''INSERT INTO accounts_task_assigned_to (id, task_id, groupid)
                              VALUES (?, ?, ?)''', (id, tid, assign_to_gr))

        conn.commit()
        cursor.close()
        conn.close()

        # Email content
        subject = f"New Task Assigned: {task_name}"
        body = f"""
        You have been assigned a new task:

        Task: {task_name}
        Description: {description}
        Start: {start_date}
        End: {end_date}
        Priority: {priority}
        Task Created by: {created_by_name}
        """
        print(body)
        message = f"Subject: {subject}\n\n{body}"

        if assign == "user":
            sendmail(user_email, message)
        else:
            for email in group_emails:
                sendmail(email, message)

        return redirect("/inserttask1")

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    conn = connect()
    cursor = conn.cursor()

    # Delete the task from the 'task' table
    cursor.execute("DELETE FROM task WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

    flash("Task deleted successfully!", "success")
    return redirect("managetask")  # Redirect back to the tasks page


@app.route('/update_task/<int:task_id>', methods=['POST'])
def update_task(task_id):
    conn = connect()
    cursor = conn.cursor()

    # Delete the task from the 'task' table
    cursor.execute("update task set status='completed' where id='%s'"%(task_id,))
    conn.commit()
    conn.close()

    flash("Task deleted successfully!", "success")
    return redirect("/managetask")  # Redirect back to the tasks page
@app.route("/groupchat", methods=["GET", "POST"])
def groupchat():
    conn = connect()
    cursor = conn.cursor()

    # Fetch all groups for dropdown
    cursor.execute("SELECT gid, groupname FROM groupsdetails")
    groups = cursor.fetchall()

    if request.method == "POST":
        from_user = session["id"]
        text = request.form["message"]
        group_id = request.form["group_id"]
        trans = datetime.now()

        cursor.execute(
            "INSERT INTO group_accounts_chat (group_id, from_user_id, text, trans) VALUES (?, ?, ?, ?)",
            (group_id, from_user, text, trans)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("groupchat", group_id=group_id))

    # GET request
    selected_group = request.args.get("group_id")
    messages = []
    group_name = None

    if selected_group:
        cursor.execute(
            "SELECT gc.from_user_id, u.username, gc.text, gc.trans FROM group_accounts_chat gc "
            "JOIN users u ON gc.from_user_id = u.uid WHERE gc.group_id = ? ORDER BY gc.trans ASC",
            (selected_group,)
        )
        messages = cursor.fetchall()

        cursor.execute("SELECT groupname FROM groupsdetails WHERE gid = ?", (selected_group,))
        row = cursor.fetchone()
        if row:
            group_name = row[0]

    conn.close()
    return render_template("groupchat.html", groups=groups, messages=messages, selected_group=selected_group, group_name=group_name)

@app.route('/profile')
def profile():
    uid = session["id"]
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE uid = ?", (uid,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template("update_profile.html", user=user)


@app.route('/updateprofile', methods=['POST'])
def updateprofile():
    uid = session["id"]
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']

    conn = connect()
    cursor = conn.cursor()
    
    if password:
        cursor.execute("UPDATE users SET username=?, email=?, password=? WHERE uid=?",
                       (username, email, password, uid))
    else:
        cursor.execute("UPDATE users SET username=?, email=? WHERE uid=?",
                       (username, email, uid))
    
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(f"/profile")


@app.route('/logout')
def logout():
    session.clear()  # Clear the session
    return redirect("/")

@app.route('/viewusers')
def viewusers():
	conn = connect()
	cursor = conn.cursor()
	cursor.execute("SELECT uid, username, email FROM users")
	users = cursor.fetchall()
	columns = [desc[0] for desc in cursor.description]
	conn.close()
	return render_template("viewusers.html", users=users, columns=columns)

@app.route('/adduser', methods=['GET', 'POST'])
def adduser():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        is_staff = int(request.form['is_staff'])
        now = datetime.now()

        conn = connect()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, email, is_staff, date_joined) VALUES (?, ?, ?, ?, ?)",
                       (username, password, email, is_staff, now))
        conn.commit()
        conn.close()
        return redirect('/viewusers')
    return render_template('addusers.html')	

@app.route('/deleteuser/<int:uid>', methods=['POST'])
def deleteuser(uid):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE uid=?", (uid,))
    conn.commit()
    conn.close()
    return redirect('/viewusers')
@app.route('/edituser/<int:uid>', methods=['GET', 'POST'])
def edituser(uid):
    conn = connect()
    cursor = conn.cursor()

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        is_staff = 0
        isapproved = 1	

        cursor.execute("""
            UPDATE users
            SET username = ?, email = ?, is_staff = ?, isapproved = ?
            WHERE uid = ?
        """, (username, email, is_staff, isapproved, uid))
        conn.commit()
        conn.close()
        return redirect('/viewusers')

    cursor.execute("SELECT uid, username, email, is_staff, isapproved FROM users WHERE uid = ?", (uid,))
    user = cursor.fetchone()
    conn.close()
    return render_template('edit_user.html', user=user)
@app.route('/insertgroupsdetails', methods=['POST'])
def insertgroupsdetails():
    groupname = request.form["groupname"]
    users = request.form.getlist("users[]")  # Get multiple users as a list

    # Handle file upload
    if "groupimage" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["groupimage"]
    file.save("static/" + file.filename)

    # Connect to SQLite database
    conn = connect()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT gid FROM groupsdetails ORDER BY gid DESC LIMIT 1")
        gid = cursor.fetchone()[0] + 1
    except:
        gid = 1

    try:
        # Insert group into database
        cursor.execute(
            "INSERT INTO groupsdetails (gid, groupname, imageicon) VALUES (?, ?, ?)",
            (gid, groupname, file.filename),
        )

        # Insert users into group_member table (assuming many-to-many relationship)
        for user_id in users:
            try:
                cursor.execute("SELECT gmid FROM group_member ORDER BY gmid DESC LIMIT 1")
                gmid = cursor.fetchone()[0] + 1
            except:
                gmid = 1

            cursor.execute("INSERT INTO group_member (gmid, gid, uid) VALUES (?, ?, ?)", 
                           (gmid, gid, user_id))

        conn.commit()
        return redirect("/inserttask1")

    except Exception as e:
        return jsonify({"error": str(e)}), 400

    finally:
        cursor.close()
        conn.close()
if __name__ == '__main__':
		app.run(debug=True)
