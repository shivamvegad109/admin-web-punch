from flask import render_template, redirect, url_for, request, flash, jsonify, current_app
from app import db
from app.models import Employee, Attendance, Notification
from app.services.db_service import DatabaseService
from app.services.notification_service import NotificationService
from . import admin_bp
from datetime import datetime, timedelta, timezone
import os
from werkzeug.utils import secure_filename

@admin_bp.route('/')
def dashboard():
    # Get counts for dashboard
    employee_count = Employee.query.count()
    today = datetime.now(timezone.utc).date()

    # Get today's attendance records
    today_records = db.session.query(
        Attendance, Employee
    ).join(Employee).filter(
        Attendance.date == today
    ).all()

    # Calculate statistics
    # Get unique employees who attended today
    unique_employees = set(emp.id for _, emp in today_records)
    attendance_today = len(unique_employees)

    # Count check-ins and check-outs
    checked_in_count = sum(1 for att, _ in today_records if att.status == 'check-in' and not att.check_out_time)
    checked_out_count = sum(1 for att, _ in today_records if att.status == 'check-out')

    # Calculate total work hours for today
    total_work_hours = sum(att.work_hours or 0 for att, _ in today_records)

    # Get recent attendance records
    recent_attendance = db.session.query(
        Attendance, Employee
    ).join(Employee).order_by(
        Attendance.check_in_time.desc()
    ).limit(10).all()

    return render_template('admin/dashboard.html',
                          employee_count=employee_count,
                          attendance_today=attendance_today,
                          recent_attendance=recent_attendance,
                          checked_in_count=checked_in_count,
                          checked_out_count=checked_out_count,
                          total_work_hours=total_work_hours)

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

    # Get total employee count
    employees_count = Employee.query.count()

    # Get attendance records for the selected date
    # Use the date field directly instead of timestamp
    attendance_records = db.session.query(
        Attendance, Employee
    ).join(Employee).filter(
        Attendance.date == selected_date
    ).order_by(Employee.name, Attendance.check_in_time).all()

    # Calculate statistics
    checked_in_count = sum(1 for att, _ in attendance_records if att.status == 'check-in')
    checked_out_count = sum(1 for att, _ in attendance_records if att.status == 'check-out')

    # Calculate total work hours for the day
    total_work_hours = sum(att.work_hours or 0 for att, _ in attendance_records)

    # Get unique employees who attended
    unique_employees = set(emp.id for _, emp in attendance_records)
    attendance_count = len(unique_employees)

    return render_template('admin/attendance.html',
                          attendance_records=attendance_records,
                          selected_date=selected_date,
                          employees_count=employees_count,
                          attendance_count=attendance_count,
                          checked_in_count=checked_in_count,
                          checked_out_count=checked_out_count,
                          total_work_hours=total_work_hours)

@admin_bp.route('/settings')
def settings():
    # Get current settings
    db_service = DatabaseService()

    # Pass current settings to template
    current_settings = {
        'work_start_hour': db_service.work_start_hour,
        'work_end_hour': db_service.work_end_hour,
        'min_hours': db_service.min_hours,
        'cooldown_minutes': db_service.cooldown_minutes,
        'enable_notifications': current_app.config.get('ENABLE_NOTIFICATIONS', False),
        'show_fps': current_app.config.get('SHOW_FPS', True),
        'enable_debug': current_app.config.get('ENABLE_DEBUG', False)
    }

    return render_template('admin/settings.html', settings=current_settings)

@admin_bp.route('/api/settings', methods=['POST'])
def update_settings():
    """API endpoint to update work hour settings"""
    try:
        data = request.json

        # Get database service
        db_service = DatabaseService()

        # Update settings
        db_service.update_work_settings(
            start_hour=int(data.get('work_start_hour', db_service.DEFAULT_WORK_START_HOUR)),
            end_hour=int(data.get('work_end_hour', db_service.DEFAULT_WORK_END_HOUR)),
            min_hours=float(data.get('min_work_hours', db_service.DEFAULT_MIN_HOURS)),
            cooldown_minutes=int(data.get('attendance_cooldown', db_service.DEFAULT_COOLDOWN_MINUTES))
        )

        # Store settings in app config for persistence
        current_app.config['WORK_START_HOUR'] = db_service.work_start_hour
        current_app.config['WORK_END_HOUR'] = db_service.work_end_hour
        current_app.config['MIN_WORK_HOURS'] = db_service.min_hours
        current_app.config['ATTENDANCE_COOLDOWN'] = db_service.cooldown_minutes

        # Update system settings
        current_app.config['ENABLE_NOTIFICATIONS'] = data.get('enable_notifications', False)
        current_app.config['SHOW_FPS'] = data.get('show_fps', True)
        current_app.config['ENABLE_DEBUG'] = data.get('enable_debug', False)

        # Create a test notification if notifications were just enabled
        if current_app.config['ENABLE_NOTIFICATIONS']:
            notification_service = NotificationService(enabled=True)
            notification_service.create_notification(
                message="Notifications are now enabled!",
                type="success",
                icon="bell"
            )

        return jsonify({'success': True, 'message': 'Settings updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/api/attendance/weekly')
def api_attendance_weekly():
    # Get attendance data for the last 7 days
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=6)

    data = []
    current_date = start_date

    while current_date <= end_date:
        # Get attendance records for this date
        daily_records = db.session.query(
            Attendance, Employee
        ).join(Employee).filter(
            Attendance.date == current_date
        ).all()

        # Get unique employees who attended
        unique_employees = set(emp.id for _, emp in daily_records)
        attendance_count = len(unique_employees)

        # Count check-ins and check-outs
        checked_in = sum(1 for att, _ in daily_records if att.status == 'check-in')
        checked_out = sum(1 for att, _ in daily_records if att.status == 'check-out')

        # Calculate total work hours
        work_hours = sum(att.work_hours or 0 for att, _ in daily_records)

        data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'count': attendance_count,
            'checked_in': checked_in,
            'checked_out': checked_out,
            'work_hours': round(work_hours, 1)
        })

        current_date += timedelta(days=1)

    return jsonify(data)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

# Notification API endpoints
@admin_bp.route('/api/notifications', methods=['GET'])
def api_get_notifications():
    """API endpoint to get notifications"""
    try:
        # Get notification service
        notification_service = NotificationService(
            enabled=current_app.config.get('ENABLE_NOTIFICATIONS', True)
        )

        # Get parameters
        limit = request.args.get('limit', 10, type=int)
        include_read = request.args.get('include_read', 'false').lower() == 'true'
        employee_id = request.args.get('employee_id', None, type=int)

        # Get notifications
        notifications = notification_service.get_notifications(
            limit=limit,
            include_read=include_read,
            employee_id=employee_id
        )

        # Convert to dict for JSON response
        notifications_data = [n.to_dict() for n in notifications]

        # Get unread count
        unread_count = Notification.query.filter_by(is_read=False).count()

        return jsonify({
            'success': True,
            'notifications': notifications_data,
            'unread_count': unread_count
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/api/notifications', methods=['POST'])
def api_create_notification():
    """API endpoint to create a notification"""
    try:
        data = request.json

        # Get notification service
        notification_service = NotificationService(
            enabled=current_app.config.get('ENABLE_NOTIFICATIONS', True)
        )

        # Create notification
        notification = notification_service.create_notification(
            message=data.get('message'),
            type=data.get('type', 'info'),
            icon=data.get('icon'),
            employee_id=data.get('employee_id')
        )

        if notification:
            return jsonify({
                'success': True,
                'notification': notification.to_dict(),
                'message': 'Notification created successfully'
            })
        else:
            return jsonify({'success': False, 'message': 'Failed to create notification'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/api/notifications/read/<int:notification_id>', methods=['POST'])
def api_mark_notification_read(notification_id):
    """API endpoint to mark a notification as read"""
    try:
        # Get notification service
        notification_service = NotificationService(
            enabled=current_app.config.get('ENABLE_NOTIFICATIONS', True)
        )

        # Mark as read
        success = notification_service.mark_as_read(notification_id)

        if success:
            # Get updated unread count
            unread_count = Notification.query.filter_by(is_read=False).count()

            return jsonify({
                'success': True,
                'message': 'Notification marked as read',
                'unread_count': unread_count
            })
        else:
            return jsonify({'success': False, 'message': 'Notification not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@admin_bp.route('/api/notifications/read-all', methods=['POST'])
def api_mark_all_notifications_read():
    """API endpoint to mark all notifications as read"""
    try:
        # Get notification service
        notification_service = NotificationService(
            enabled=current_app.config.get('ENABLE_NOTIFICATIONS', True)
        )

        # Get employee_id parameter if provided
        employee_id = request.json.get('employee_id') if request.json else None

        # Mark all as read
        count = notification_service.mark_all_as_read(employee_id)

        return jsonify({
            'success': True,
            'message': f'{count} notifications marked as read',
            'unread_count': 0
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
