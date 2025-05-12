import face_recognition
import mediapipe as mp
import numpy as np
import time
import pickle
import cv2
from threading import Thread, Lock
from queue import Queue
from app import logger
from app.services.db_service import DatabaseService
from flask import current_app

class OptimizedFaceService:
    def __init__(self, app=None):
        # Initialize MediaPipe face detection (faster than HOG)
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=1,  # 0 for close range, 1 for far range
            min_detection_confidence=0.6  # Lower threshold for better detection
        )
        
        # Initialize face mesh for more accurate landmarks (optional)
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=10,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # State variables
        self.faces = []
        self.face_lock = Lock()
        self.running = False
        self.thread = None
        self.db_service = DatabaseService()
        self.employee_profiles = []
        self.app = app
        
        # Performance optimization variables
        self.frame_skip = 2  # Process every nth frame
        self.frame_count = 0
        self.last_encodings = {}  # Cache for face encodings
        self.encoding_ttl = 50  # Frames before refreshing encoding
        self.last_attendance_time = {}  # Track last attendance for each employee
        self.attendance_cooldown = 300  # 5 minutes in seconds
        
        # Visualization settings
        self.show_landmarks = False
        self.show_fps = True
        self.fps_values = []
        self.last_fps_time = time.time()

    def start(self, frame_queue):
        if self.running:
            return
            
        self.running = True
        self.frame_queue = frame_queue
        
        # Load employee profiles
        self.employee_profiles = self.db_service.load_employee_encodings()
        
        # Start processing thread
        self.thread = Thread(target=self._detection_loop, daemon=True)
        self.thread.start()
        logger.info("Optimized face detection started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Face detection stopped")

    def _detection_loop(self):
        last_time = time.time()
        
        while self.running:
            if self.frame_queue.empty():
                time.sleep(0.01)
                continue
                
            # Get frame from queue
            rgb_frame = self.frame_queue.get()
            self.frame_count += 1
            
            # Skip frames for performance
            if self.frame_count % self.frame_skip != 0:
                continue
                
            # Calculate FPS
            current_time = time.time()
            fps = 1 / (current_time - last_time) if (current_time - last_time) > 0 else 0
            self.fps_values.append(fps)
            if len(self.fps_values) > 30:
                self.fps_values.pop(0)
            last_time = current_time
            
            # Process frame
            detected_faces = self._process_frame(rgb_frame)
            
            # Update faces with lock
            with self.face_lock:
                self.faces = detected_faces

    def _process_frame(self, rgb_frame):
        detected_faces = []
        h, w, _ = rgb_frame.shape
        
        # Detect faces using MediaPipe (faster)
        results = self.face_detection.process(rgb_frame)
        
        if not results.detections:
            return []
            
        # Extract face locations
        face_locations = []
        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            x = max(0, int(bbox.xmin * w))
            y = max(0, int(bbox.ymin * h))
            width = min(int(bbox.width * w), w - x)
            height = min(int(bbox.height * h), h - y)
            
            # Convert to face_recognition format (top, right, bottom, left)
            face_locations.append((y, x + width, y + height, x))
        
        # Get face encodings (expensive operation)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations, num_jitters=1, model="small")
        
        # Match faces with employees
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            label = "Unknown"
            employee_id = None
            confidence = 0
            
            # Compare with known employees
            for employee in self.employee_profiles:
                # Use distance for better matching
                face_distances = face_recognition.face_distance([employee["encoding"]], face_encoding)
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    current_confidence = 1 - face_distances[best_match_index]
                    
                    if current_confidence > 0.6 and current_confidence > confidence:  # Adjust threshold as needed
                        confidence = current_confidence
                        label = f"{employee['name']} ({int(confidence*100)}%)"
                        employee_id = employee["id"]
            
            # Log attendance if recognized
            if employee_id is not None:
                current_time = time.time()
                last_time = self.last_attendance_time.get(employee_id, 0)
                
                # Check if cooldown period has passed
                if current_time - last_time > self.attendance_cooldown:
                    self.last_attendance_time[employee_id] = current_time
                    
                    # Use app context for database operations
                    if self.app:
                        with self.app.app_context():
                            self.db_service.log_attendance(employee_id)
            
            # Add to detected faces
            detected_faces.append((left, top, right - left, bottom - top, label))
        
        return detected_faces

    def generate_frames(self, original_frame):
        """Enhanced frame generation with additional information"""
        with self.face_lock:
            faces = self.faces.copy()
        
        # Draw faces and information
        for (x, y, w, h, label) in faces:
            # Determine color based on recognition
            if "Unknown" in label:
                color = (255, 0, 0)  # Red for unknown
            else:
                color = (0, 255, 0)  # Green for known
                
            # Draw face rectangle
            cv2.rectangle(original_frame, (x, y), (x + w, y + h), color, 2)
            
            # Draw label with better visibility
            cv2.rectangle(original_frame, (x, y - 30), (x + w, y), color, -1)
            cv2.putText(original_frame, label, (x + 6, y - 6), 
                       cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)
        
        # Add FPS counter
        if self.show_fps and self.fps_values:
            avg_fps = sum(self.fps_values) / len(self.fps_values)
            cv2.putText(original_frame, f"FPS: {avg_fps:.1f}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        return original_frame
