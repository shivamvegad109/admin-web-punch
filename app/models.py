from datetime import datetime
from app import db

# Helper function for timestamp default value
def get_utc_now():
    # This is the recommended way, but we're keeping it timezone-naive for compatibility
    return datetime.utcnow()

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

    def __repr__(self):
        return f'<Employee {self.name}>'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=get_utc_now)

    def __repr__(self):
        return f'<Attendance {self.employee_id} at {self.timestamp}>'