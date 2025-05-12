from flask import render_template, redirect, url_for, request, flash, jsonify, current_app
from app import db
from app.models import Employee, Attendance
from app.services.db_service import DatabaseService
from . import admin_bp
from datetime import datetime, timedelta, timezone
import os
from werkzeug.utils import secure_filename

@admin_bp.route('/')
def dashboard():
    # Get counts for dashboard
    employee_count = Employee.query.count()
    today = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    attendance_today = Attendance.query.filter(
        Attendance.timestamp >= today_start,
        Attendance.timestamp <= today_end
    ).count()

    # Get recent attendance records
    recent_attendance = db.session.query(
        Attendance, Employee
    ).join(Employee).order_by(
        Attendance.timestamp.desc()
    ).limit(10).all()

    return render_template('admin/dashboard.html',
                          employee_count=employee_count,
                          attendance_today=attendance_today,
                          recent_attendance=recent_attendance)

@admin_bp.route('/employees')
def employees():
    employees_list = Employee.query.all()
    return render_template('admin/employees.html', employees=employees_list)

@admin_bp.route('/employees/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        name = request.form.get('name')
        position = request.form.get('position', '')
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')

        if 'photo' not in request.files or not name:
            flash('Name and photo are required.', 'danger')
            return redirect(request.url)

        file = request.files['photo']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            # Create a database service instance
            db_service = DatabaseService()
            if db_service.add_employee(name, file_path, position, email, phone):
                flash(f'Employee {name} added successfully.', 'success')
                return redirect(url_for('admin.employees'))
            else:
                flash(f'Failed to add employee {name}. No face detected.', 'danger')

        else:
            flash('Invalid file type. Allowed: jpg, jpeg, png.', 'danger')

    return render_template('admin/add_employee.html')

@admin_bp.route('/employees/edit/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    employee = Employee.query.get_or_404(id)

    if request.method == 'POST':
        employee.name = request.form.get('name')
        employee.position = request.form.get('position', '')
        employee.email = request.form.get('email', '')
        employee.phone = request.form.get('phone', '')

        if 'photo' in request.files and request.files['photo'].filename != '':
            file = request.files['photo']
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = current_app.config['UPLOAD_FOLDER']
                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)

                # Update face encoding
                db_service = DatabaseService()
                if not db_service.update_employee_photo(employee.id, file_path):
                    flash('Failed to update photo. No face detected.', 'danger')
                    return redirect(request.url)
            else:
                flash('Invalid file type. Allowed: jpg, jpeg, png.', 'danger')
                return redirect(request.url)

        db.session.commit()
        flash(f'Employee {employee.name} updated successfully.', 'success')
        return redirect(url_for('admin.employees'))

    return render_template('admin/edit_employee.html', employee=employee)

@admin_bp.route('/employees/delete/<int:id>', methods=['POST'])
def delete_employee(id):
    employee = Employee.query.get_or_404(id)
    name = employee.name

    db.session.delete(employee)
    db.session.commit()

    flash(f'Employee {name} deleted successfully.', 'success')
    return redirect(url_for('admin.employees'))

@admin_bp.route('/attendance')
def attendance():
    # Default to today's date
    date_str = request.args.get('date', datetime.now(timezone.utc).strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = datetime.now(timezone.utc).date()

    date_start = datetime.combine(selected_date, datetime.min.time())
    date_end = datetime.combine(selected_date, datetime.max.time())

    # Get total employee count
    employees_count = Employee.query.count()

    attendance_records = db.session.query(
        Attendance, Employee
    ).join(Employee).filter(
        Attendance.timestamp >= date_start,
        Attendance.timestamp <= date_end
    ).order_by(Employee.name).all()

    return render_template('admin/attendance.html',
                          attendance_records=attendance_records,
                          selected_date=selected_date,
                          employees_count=employees_count)

@admin_bp.route('/settings')
def settings():
    return render_template('admin/settings.html')

@admin_bp.route('/api/attendance/weekly')
def api_attendance_weekly():
    # Get attendance data for the last 7 days
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=6)

    data = []
    current_date = start_date

    while current_date <= end_date:
        date_start = datetime.combine(current_date, datetime.min.time())
        date_end = datetime.combine(current_date, datetime.max.time())

        count = Attendance.query.filter(
            Attendance.timestamp >= date_start,
            Attendance.timestamp <= date_end
        ).count()

        data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'count': count
        })

        current_date += timedelta(days=1)

    return jsonify(data)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
