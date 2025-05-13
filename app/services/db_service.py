import pickle
import cv2
import numpy as np
from datetime import datetime, timedelta, timezone
from app import db, logger
from app.models import Employee, Attendance

class DatabaseService:
    # Default work hour settings
    DEFAULT_WORK_START_HOUR = 9  # 9 AM
    DEFAULT_WORK_END_HOUR = 17   # 5 PM
    DEFAULT_MIN_HOURS = 1        # Minimum hours between check-in and check-out
    DEFAULT_COOLDOWN_MINUTES = 5 # Minimum minutes between attendance logs

    def __init__(self):
        # Initialize with default settings
        self.work_start_hour = self.DEFAULT_WORK_START_HOUR
        self.work_end_hour = self.DEFAULT_WORK_END_HOUR
        self.min_hours = self.DEFAULT_MIN_HOURS
        self.cooldown_minutes = self.DEFAULT_COOLDOWN_MINUTES

    def update_work_settings(self, start_hour=None, end_hour=None, min_hours=None, cooldown_minutes=None):
        """Update work hour settings"""
        if start_hour is not None:
            self.work_start_hour = start_hour
        if end_hour is not None:
            self.work_end_hour = end_hour
        if min_hours is not None:
            self.min_hours = min_hours
        if cooldown_minutes is not None:
            self.cooldown_minutes = cooldown_minutes

        logger.info(f"Updated work settings: Start={self.work_start_hour}h, End={self.work_end_hour}h, " +
                   f"Min Hours={self.min_hours}h, Cooldown={self.cooldown_minutes}min")

    def load_employee_encodings(self):
        """
        Load employee face encodings with enhanced error handling for office environment
        """
        try:
            # Don't create a new app context, use the existing one
            employees = Employee.query.all()
            employee_profiles = []

            for emp in employees:
                try:
                    encoding = pickle.loads(emp.face_encoding)

                    # Validate encoding format
                    if not isinstance(encoding, np.ndarray):
                        logger.warning(f"Invalid encoding format for employee {emp.name} (ID: {emp.id})")
                        continue

                    # Check encoding dimensions
                    if encoding.shape[0] != 128:  # Face encodings should be 128-dimensional
                        logger.warning(f"Invalid encoding dimensions for employee {emp.name} (ID: {emp.id})")
                        continue

                    employee_profiles.append({
                        "id": emp.id,
                        "name": emp.name,
                        "position": emp.position,
                        "encoding": encoding,
                        "email": emp.email,
                        "phone": emp.phone
                    })
                except Exception as e:
                    logger.error(f"Failed to load encoding for employee {emp.name} (ID: {emp.id}): {e}")
                    continue

            logger.info(f"Loaded {len(employee_profiles)} employee profiles.")
            return employee_profiles
        except Exception as e:
            logger.error(f"Failed to load employee encodings: {e}")
            return []

    def add_employee(self, name, image_path, position='', email='', phone=''):
        """
        Add a new employee with enhanced face encoding for better recognition in office environments
        """
        import face_recognition
        try:
            # Load and preprocess the image
            image = self._preprocess_image(image_path)
            if image is None:
                logger.error(f"Failed to preprocess image for {name}.")
                return False

            # Detect faces with higher accuracy settings
            face_locations = face_recognition.face_locations(image, model="hog")
            if not face_locations:
                logger.error(f"No face found in image for {name}.")
                return False

            # If multiple faces found, use the largest one
            if len(face_locations) > 1:
                logger.warning(f"Multiple faces found in image for {name}. Using the largest face.")
                largest_face = self._get_largest_face(face_locations)
                face_locations = [largest_face]

            # Generate face encoding with higher quality settings
            encodings = face_recognition.face_encodings(image, face_locations, num_jitters=10, model="large")
            if not encodings:
                logger.error(f"Failed to generate face encoding for {name}.")
                return False

            encoding = encodings[0]
            encoding_blob = pickle.dumps(encoding)

            # Create and save employee record
            employee = Employee(
                name=name,
                face_encoding=encoding_blob,
                position=position,
                email=email,
                phone=phone
            )
            db.session.add(employee)
            db.session.commit()

            logger.info(f"Added employee {name} with high-quality face encoding.")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to add employee {name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def update_employee_photo(self, employee_id, image_path):
        """
        Update employee photo with enhanced face encoding for better recognition
        """
        import face_recognition
        try:
            # Load and preprocess the image
            image = self._preprocess_image(image_path)
            if image is None:
                logger.error(f"Failed to preprocess image for employee ID {employee_id}.")
                return False

            # Detect faces with higher accuracy settings
            face_locations = face_recognition.face_locations(image, model="hog")
            if not face_locations:
                logger.error(f"No face found in image for employee ID {employee_id}.")
                return False

            # If multiple faces found, use the largest one
            if len(face_locations) > 1:
                logger.warning(f"Multiple faces found in image for employee ID {employee_id}. Using the largest face.")
                largest_face = self._get_largest_face(face_locations)
                face_locations = [largest_face]

            # Generate face encoding with higher quality settings
            encodings = face_recognition.face_encodings(image, face_locations, num_jitters=10, model="large")
            if not encodings:
                logger.error(f"Failed to generate face encoding for employee ID {employee_id}.")
                return False

            encoding = encodings[0]
            encoding_blob = pickle.dumps(encoding)

            # Update employee record
            employee = Employee.query.get(employee_id)
            if not employee:
                logger.error(f"Employee with ID {employee_id} not found.")
                return False

            employee.face_encoding = encoding_blob
            employee.updated_at = datetime.now(timezone.utc)
            db.session.commit()

            logger.info(f"Updated photo for employee {employee.name} with high-quality face encoding.")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to update employee photo: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _preprocess_image(self, image_path):
        """
        Preprocess image for better face recognition in office environments
        """
        try:
            # Load image using face_recognition library
            import face_recognition
            image = face_recognition.load_image_file(image_path)

            # Convert to RGB if needed
            if len(image.shape) == 2:  # Grayscale
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 4:  # RGBA
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)

            # Check image size and resize if too large
            max_size = 1024
            h, w = image.shape[:2]
            if h > max_size or w > max_size:
                scale = max_size / max(h, w)
                new_size = (int(w * scale), int(h * scale))
                image = cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)

            # Apply image enhancements for better face recognition
            # Convert to LAB color space for better processing
            lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)

            # Split channels
            l, a, b = cv2.split(lab)

            # Apply CLAHE to L channel for better contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)

            # Merge channels
            enhanced_lab = cv2.merge((cl, a, b))

            # Convert back to RGB
            enhanced_image = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)

            return enhanced_image

        except Exception as e:
            logger.error(f"Image preprocessing error: {e}")
            return None

    def _get_largest_face(self, face_locations):
        """
        Get the largest face from a list of face locations
        """
        largest_area = 0
        largest_face = None

        for face in face_locations:
            top, right, bottom, left = face
            area = (bottom - top) * (right - left)

            if area > largest_area:
                largest_area = area
                largest_face = face

        return largest_face

    def log_attendance(self, employee_id):
        """
        Log employee attendance with check-in/check-out functionality
        """
        try:
            # Get employee details
            employee = Employee.query.get(employee_id)
            if not employee:
                logger.error(f"Cannot log attendance: Employee with ID {employee_id} not found.")
                return False

            # Get current time (timezone-aware)
            current_time = datetime.now(timezone.utc)
            current_date = current_time.date()

            # Find today's attendance record for this employee
            today_record = Attendance.query.filter_by(
                employee_id=employee_id,
                date=current_date
            ).first()

            # Work hour settings are now instance variables
            # self.work_start_hour, self.work_end_hour, self.min_hours, self.cooldown_minutes

            # Check if we need to create a new record or update existing one
            if not today_record:
                # No record for today - create a new check-in
                attendance = Attendance(
                    employee_id=employee_id,
                    check_in_time=current_time,
                    status='check-in',
                    date=current_date
                )
                db.session.add(attendance)
                db.session.commit()
                logger.info(f"Logged check-in for {employee.name} (ID: {employee_id}) at {current_time}.")
                return {'action': 'check-in', 'time': current_time}

            # We have a record for today
            # Determine if this should be a check-out or if it's too soon after check-in
            if today_record.status == 'check-in' and not today_record.check_out_time:
                # Calculate time since check-in
                time_since_checkin = current_time - today_record.check_in_time

                # Check if enough time has passed for a valid check-out
                if time_since_checkin.total_seconds() < (self.min_hours * 3600):
                    # Too soon for check-out, treat as duplicate check-in
                    if time_since_checkin.total_seconds() < (self.cooldown_minutes * 60):
                        logger.info(f"Skipping duplicate check-in for {employee.name}: recent entry exists.")
                        return {'action': 'skip', 'reason': 'recent-checkin'}

                    # It's been more than cooldown but less than minimum hours - update check-in time
                    today_record.check_in_time = current_time
                    db.session.commit()
                    logger.info(f"Updated check-in time for {employee.name} to {current_time}.")
                    return {'action': 'update-checkin', 'time': current_time}

                # Enough time has passed, record check-out
                today_record.check_out_time = current_time
                today_record.status = 'check-out'
                today_record.update_work_hours()
                db.session.commit()
                logger.info(f"Logged check-out for {employee.name} (ID: {employee_id}) at {current_time}.")
                return {'action': 'check-out', 'time': current_time, 'hours': today_record.work_hours}

            # Already checked out today
            if today_record.status == 'check-out' and today_record.check_out_time:
                # Check if enough time has passed since check-out
                time_since_checkout = current_time - today_record.check_out_time

                if time_since_checkout.total_seconds() < (self.cooldown_minutes * 60):
                    logger.info(f"Skipping attendance log for {employee.name}: already checked out today.")
                    return {'action': 'skip', 'reason': 'already-checkout'}

                # It's been long enough - create a new check-in record
                # This handles cases where someone leaves and comes back same day
                attendance = Attendance(
                    employee_id=employee_id,
                    check_in_time=current_time,
                    status='check-in',
                    date=current_date
                )
                db.session.add(attendance)
                db.session.commit()
                logger.info(f"Logged additional check-in for {employee.name} (ID: {employee_id}) at {current_time}.")
                return {'action': 'additional-checkin', 'time': current_time}

            # Fallback - should not reach here in normal operation
            logger.warning(f"Unexpected attendance state for {employee.name} (ID: {employee_id}).")
            return {'action': 'error', 'reason': 'unexpected-state'}

        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to log attendance: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {'action': 'error', 'reason': str(e)}
