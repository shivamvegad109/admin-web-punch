from datetime import datetime, timezone
from app import db

# Helper function for timestamp default value
def get_utc_now():
    """Get current UTC time (timezone-aware)"""
    # Use timezone-aware datetime
    return datetime.now(timezone.utc)

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    face_encoding = db.Column(db.LargeBinary, nullable=False)
    position = db.Column(db.String(255), default='')
    email = db.Column(db.String(255), default='')
    phone = db.Column(db.String(50), default='')
    created_at = db.Column(db.DateTime, nullable=False, default=get_utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=get_utc_now, onupdate=get_utc_now)
    attendances = db.relationship('Attendance', backref='employee', lazy=True)
    notifications = db.relationship('Notification', backref='employee', lazy=True)

    def __repr__(self):
        return f'<Employee {self.name}>'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    check_in_time = db.Column(db.DateTime, nullable=False, default=get_utc_now)
    check_out_time = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='check-in')  # 'check-in', 'check-out', 'absent'
    work_hours = db.Column(db.Float, nullable=True)  # Hours worked (calculated on check-out)
    date = db.Column(db.Date, nullable=False, default=lambda: get_utc_now().date())

    # For backward compatibility
    @property
    def timestamp(self):
        return self.check_in_time

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), default='info')  # 'info', 'success', 'warning', 'danger'
    icon = db.Column(db.String(50), default='fa-info-circle')  # FontAwesome icon class
    is_read = db.Column(db.Boolean, default=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=get_utc_now)

    def __repr__(self):
        return f'<Notification {self.id}: {self.message[:20]}...>'

    def to_dict(self):
        """Convert notification to dictionary for JSON response"""
        return {
            'id': self.id,
            'message': self.message,
            'type': self.type,
            'icon': self.icon,
            'is_read': self.is_read,
            'employee_id': self.employee_id,
            'employee_name': self.employee.name if self.employee else None,
            'created_at': self.created_at.isoformat(),
            'time_ago': self.get_time_ago()
        }

    def get_time_ago(self):
        """Return a human-readable time difference"""
        # Make sure both datetimes are timezone-aware
        now = get_utc_now()
        created_at = self.created_at

        # Ensure created_at is timezone-aware
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        diff = now - created_at

        seconds = diff.total_seconds()
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f"{days} day{'s' if days > 1 else ''} ago"
        else:
            return created_at.strftime("%b %d, %Y")

    def calculate_work_hours(self):
        """Calculate work hours if check-out time is available"""
        if self.check_out_time and self.check_in_time:
            delta = self.check_out_time - self.check_in_time
            # Convert to hours (as decimal)
            return round(delta.total_seconds() / 3600, 2)
        return None

    def update_work_hours(self):
        """Update work hours based on check-in and check-out times"""
        self.work_hours = self.calculate_work_hours()

    def __repr__(self):
        if self.check_out_time:
            return f'<Attendance {self.employee_id} from {self.check_in_time} to {self.check_out_time}>'
        return f'<Attendance {self.employee_id} checked in at {self.check_in_time}>'