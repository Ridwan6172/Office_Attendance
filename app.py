from flask import Flask, render_template, request, redirect, flash, send_file
from datetime import date
from db_config import get_connection
from utils import get_bd_time, calculate_status
from flask import session
import calendar
import pandas as pd
from flask import send_file
from io import BytesIO

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Needed for flash messages

@app.route('/')
def home():
    return redirect('/employee')

@app.route('/admin/download-individual-report/<emp_id>', methods=['GET'])
def download_individual_report(emp_id):
    if 'admin' not in session:
        return redirect('/admin/login')

    # Connect to the database
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch the employee details
    cursor.execute("SELECT * FROM employees WHERE employee_id = %s", (emp_id,))
    employee = cursor.fetchone()

    if not employee:
        flash("Employee not found.", "danger")
        return redirect('/admin/report')

    # Fetch the attendance records for the employee
    cursor.execute("SELECT * FROM attendance WHERE employee_id = %s", (emp_id,))
    records = cursor.fetchall()

    cursor.close()
    conn.close()

    # Convert the records into a pandas DataFrame
    df = pd.DataFrame(records)

    # Create a CSV from the DataFrame
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)

    # Create a filename for the CSV
    filename = f"{employee['name'].replace(' ', '_')}_attendance_report.csv"


    # Return the CSV file as a downloadable response
    return send_file(output, mimetype='text/csv', download_name=filename, as_attachment=True)




@app.route('/employee', methods=['GET', 'POST'])
def employee_portal():
    if request.method == 'POST':
        emp_id = request.form.get('employee_id')
        action = request.form.get('action')
        now = get_bd_time()

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM employees WHERE employee_id = %s", (emp_id,))
        emp = cursor.fetchone()

        if not emp:
            flash("Employee ID not found.", "danger")
            return redirect('/employee')

        today = date.today()

        cursor.execute("SELECT * FROM attendance WHERE employee_id = %s AND date = %s", (emp_id, today))
        record = cursor.fetchone()

        if action == "in":
            if record:
                flash("Already signed in today.", "info")
            else:
                status = calculate_status(now)
                cursor.execute("INSERT INTO attendance (employee_id, date, sign_in, status) VALUES (%s, %s, %s, %s)",
                               (emp_id, today, now.time(), status))
                conn.commit()
                flash(f"Signed in as {status}.", "success")

        elif action == "out":
            if not record:
                flash("You have not signed in today.", "warning")
            elif record['sign_out']:
                flash("Already signed out today.", "info")
            else:
                cursor.execute("UPDATE attendance SET sign_out = %s WHERE id = %s", (now.time(), record['id']))
                conn.commit()
                flash("Signed out successfully.", "success")

        cursor.close()
        conn.close()
    return render_template('employee_portal.html')
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == "admin" and password == "admin123":
            session['admin'] = True
            return redirect('/admin/dashboard')
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin/login')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin/login')

    today = date.today()
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM attendance WHERE date = %s", (today,))
    total = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS present FROM attendance WHERE date = %s AND status = 'Present'", (today,))
    present = cursor.fetchone()['present']

    cursor.execute("SELECT COUNT(*) AS late FROM attendance WHERE date = %s AND status = 'Late'", (today,))
    late = cursor.fetchone()['late']

    cursor.execute("SELECT COUNT(*) AS absent FROM employees")
    total_emp = cursor.fetchone()['absent']

    # Subtract those who are present/late from total employees to get absents
    absent = total_emp - (present + late)

    cursor.close()
    conn.close()

    return render_template("dashboard.html", present=present, late=late, absent=absent)

@app.route('/admin/report', methods=['GET', 'POST'])
def all_reports():
    if 'admin' not in session:
        return redirect('/admin/login')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    selected_month = request.form.get('month') if request.method == 'POST' else None
    query = """
        SELECT a.*, e.name, e.department
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
    """
    params = ()
    
    if selected_month:
        year, month = selected_month.split("-")
        query += " WHERE MONTH(date) = %s AND YEAR(date) = %s"
        params = (int(month), int(year))

    query += " ORDER BY date DESC"
    cursor.execute(query, params)
    records = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("all_report.html", records=records, selected_month=selected_month)

@app.route('/download-csv')
def download_csv():
    if 'admin' not in session:
        return redirect('/admin/login')

    selected_month = request.args.get('month')
    emp_id = request.args.get('emp_id')

    query = """
        SELECT a.date, a.employee_id, e.name, e.department, a.sign_in, a.sign_out, a.status
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
    """
    conditions = []
    params = []

    if emp_id:
        conditions.append("a.employee_id = %s")
        params.append(emp_id)

    if selected_month:
        year, month = selected_month.split("-")
        conditions.append("MONTH(a.date) = %s AND YEAR(a.date) = %s")
        params.extend([int(month), int(year)])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    headers = [i[0] for i in cursor.description]
    cursor.close()
    conn.close()

    df = pd.DataFrame(rows, columns=headers)
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)

    filename = f"{emp_id or 'all'}_attendance_{selected_month or 'all'}.csv"
    return send_file(output, mimetype='text/csv', download_name=filename, as_attachment=True)


@app.route('/admin/employee/<emp_id>', methods=['GET', 'POST'])
def individual_report(emp_id):
    if 'admin' not in session:
        return redirect('/admin/login')

    selected_month = request.form.get('month') if request.method == 'POST' else None
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM employees WHERE employee_id = %s", (emp_id,))
    employee = cursor.fetchone()

    if not employee:
        flash("Employee not found.", "danger")
        return redirect('/admin/report')

    query = "SELECT * FROM attendance WHERE employee_id = %s"
    params = [emp_id]

    if selected_month:
        year, month = selected_month.split("-")
        query += " AND MONTH(date) = %s AND YEAR(date) = %s"
        params += [int(month), int(year)]

    query += " ORDER BY date DESC"
    cursor.execute(query, params)
    records = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("employee_report.html", employee=employee, records=records, selected_month=selected_month)

@app.route('/admin/add-employee', methods=['GET', 'POST'])
def add_employee():
    if 'admin' not in session:
        return redirect('/admin/login')

    if request.method == 'POST':
        employee_id = request.form.get('employee_id')
        name = request.form.get('name')
        department = request.form.get('department')
        email = request.form.get('email')
        password = request.form.get('password')

        if not employee_id or not name or not department or not email or not password:
            flash("All fields are required!", "danger")
            return redirect('/admin/add-employee')

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO employees (employee_id, name, department, email, password) VALUES (%s, %s, %s, %s, %s)",
                       (employee_id, name, department, email, password))
        conn.commit()
        cursor.close()
        conn.close()

        flash(f"Employee {name} added successfully!", "success")
        return redirect('/admin/dashboard')

    return render_template("add_employee.html")

@app.route('/admin/edit-attendance/<attendance_id>', methods=['GET', 'POST'])
def edit_attendance(attendance_id):
    if 'admin' not in session:
        return redirect('/admin/login')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance WHERE id = %s", (attendance_id,))  # Changed here
    record = cursor.fetchone()

    if not record:
        flash("Attendance record not found.", "danger")
        return redirect('/admin/report')

    if request.method == 'POST':
        status = request.form.get('status')
        sign_in = request.form.get('sign_in')
        sign_out = request.form.get('sign_out')

        if status:
            cursor.execute("UPDATE attendance SET status = %s WHERE id = %s", (status, attendance_id))  # Changed here
        if sign_in:
            cursor.execute("UPDATE attendance SET sign_in = %s WHERE id = %s", (sign_in, attendance_id))  # Changed here
        if sign_out:
            cursor.execute("UPDATE attendance SET sign_out = %s WHERE id = %s", (sign_out, attendance_id))  # Changed here

        conn.commit()
        cursor.close()
        conn.close()

        flash("Attendance updated successfully!", "success")
        return redirect(f"/admin/employee/{record['employee_id']}")

    cursor.close()
    conn.close()

    return render_template("edit_attendance.html", record=record)


if __name__ == "__main__":
    app.run(debug=True)





