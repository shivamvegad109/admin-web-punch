import pickle
from datetime import datetime, timedelta, timezone
from app import db, logger
from app.models import Employee, Attendance

class DatabaseService:
    def load_employee_encodings(self):
        try:
            # Don't create a new app context, use the existing one
            employees = Employee.query.all()
            employee_profiles = []
            for emp in employees:
                encoding = pickle.loads(emp.face_encoding)
                employee_profiles.append({
                    "id": emp.id,
                    "name": emp.name,
                    "encoding": encoding
                })
            logger.info(f"Loaded {len(employee_profiles)} employee profiles.")
            return employee_profiles
        except Exception as e:
            logger.error(f"Failed to load employee encodings: {e}")
            return []

    def add_employee(self, name, image_path, position='', email='', phone=''):
        import face_recognition
        try:
            image = face_recognition.load_image_file(image_path)
            encodings = face_recognition.face_encodings(image, num_jitters=5)
            if not encodings:
                logger.error(f"No face found in image for {name}.")
                return False

            encoding = encodings[0]
            encoding_blob = pickle.dumps(encoding)

            employee = Employee(
                name=name,
                face_encoding=encoding_blob,
                position=position,
                email=email,
                phone=phone
            )
            db.session.add(employee)
            db.session.commit()

            logger.info(f"Added employee {name}.")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to add employee {name}: {e}")
            return False

    def update_employee_photo(self, employee_id, image_path):
        import face_recognition
        try:
            image = face_recognition.load_image_file(image_path)
            encodings = face_recognition.face_encodings(image, num_jitters=5)
            if not encodings:
                logger.error(f"No face found in image for employee ID {employee_id}.")
                return False

            encoding = encodings[0]
            encoding_blob = pickle.dumps(encoding)

            employee = Employee.query.get(employee_id)
            if not employee:
                logger.error(f"Employee with ID {employee_id} not found.")
                return False

            employee.face_encoding = encoding_blob
            db.session.commit()

            logger.info(f"Updated photo for employee {employee.name}.")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update employee photo: {e}")
            return False

    def log_attendance(self, employee_id):
        try:
            # Check last entry
            last_entry = Attendance.query.filter_by(
                employee_id=employee_id
            ).order_by(Attendance.timestamp.desc()).first()

            # Use timezone-naive datetime to match the database
            current_time = datetime.utcnow()
            if last_entry and (current_time - last_entry.timestamp) < timedelta(minutes=5):
                return

            # Add new attendance record
            attendance = Attendance(employee_id=employee_id)
            db.session.add(attendance)
            db.session.commit()

            logger.info(f"Logged attendance for employee ID {employee_id}.")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to log attendance: {e}")
