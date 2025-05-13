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
from collections import defaultdict

class OptimizedFaceService:
    def __init__(self, app=None):
        # Initialize MediaPipe face detection (faster than HOG)
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=1,  # 0 for close range, 1 for far range
            min_detection_confidence=0.5  # Lower threshold for better detection in office environments
        )

        # Initialize face mesh for more accurate landmarks
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=10,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # Drawing utilities for face mesh visualization
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        # State variables
        self.faces = []
        self.face_lock = Lock()
        self.running = False
        self.thread = None
        self.db_service = DatabaseService()
        self.employee_profiles = []
        self.app = app
        self.frame_queue = None

        # Performance optimization variables
        self.frame_skip = 1  # Process every frame for office cameras (more reliable)
        self.frame_count = 0
        self.face_cache = defaultdict(dict)  # Cache for face tracking
        self.encoding_ttl = 30  # Frames before refreshing encoding (reduced for better accuracy)
        self.last_attendance_time = {}  # Track last attendance for each employee
        self.attendance_cooldown = 180  # 3 minutes in seconds (reduced for office environment)

        # Face tracking variables
        self.face_trackers = {}  # Track faces across frames
        self.next_face_id = 0
        self.max_tracking_age = 30  # Maximum frames to keep tracking a face

        # Recognition settings
        self.recognition_threshold = 0.55  # Lower threshold for better recognition in office
        self.use_small_model = True  # Use small model for faster processing
        self.jitter_count = 1  # Number of times to re-sample face for encoding

        # Visualization settings
        self.show_landmarks = True  # Show facial landmarks for better visualization
        self.show_fps = True
        self.fps_values = []
        self.last_fps_time = time.time()
        self.show_recognition_score = True  # Show confidence score

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
        """
        Enhanced face processing with tracking and optimized recognition
        """
        detected_faces = []
        h, w, _ = rgb_frame.shape

        # Update face trackers age and remove old ones
        faces_to_delete = []
        for face_id, tracker_data in self.face_trackers.items():
            tracker_data['age'] += 1
            if tracker_data['age'] > self.max_tracking_age:
                faces_to_delete.append(face_id)

        for face_id in faces_to_delete:
            del self.face_trackers[face_id]

        # Detect faces using MediaPipe (faster than HOG)
        results = self.face_detection.process(rgb_frame)

        if not results.detections:
            # If no faces detected but we have trackers, use the last known positions
            if self.face_trackers:
                for face_id, tracker_data in self.face_trackers.items():
                    if tracker_data['age'] < 10:  # Only use recent trackers
                        detected_faces.append((
                            tracker_data['bbox'][0],
                            tracker_data['bbox'][1],
                            tracker_data['bbox'][2],
                            tracker_data['bbox'][3],
                            tracker_data['label']
                        ))
            return detected_faces

        # Process detected faces
        current_face_locations = []
        current_face_bboxes = []

        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            x = max(0, int(bbox.xmin * w))
            y = max(0, int(bbox.ymin * h))
            width = min(int(bbox.width * w), w - x)
            height = min(int(bbox.height * h), h - y)

            # Store both formats
            current_face_locations.append((y, x + width, y + height, x))  # face_recognition format
            current_face_bboxes.append((x, y, width, height))  # Our bbox format

        # Match current detections with existing trackers
        if self.face_trackers:
            # Calculate IoU between current detections and existing trackers
            matched_faces = {}
            unmatched_detections = list(range(len(current_face_bboxes)))

            for face_id, tracker_data in self.face_trackers.items():
                best_iou = 0.3  # Minimum IoU threshold
                best_match = -1

                for i, bbox in enumerate(current_face_bboxes):
                    iou = self._calculate_iou(tracker_data['bbox'], bbox)
                    if iou > best_iou:
                        best_iou = iou
                        best_match = i

                if best_match >= 0:
                    matched_faces[face_id] = best_match
                    if best_match in unmatched_detections:
                        unmatched_detections.remove(best_match)

            # Update matched trackers
            for face_id, detection_idx in matched_faces.items():
                self.face_trackers[face_id]['bbox'] = current_face_bboxes[detection_idx]
                self.face_trackers[face_id]['age'] = 0

                # Only re-encode face if TTL expired
                if self.face_trackers[face_id]['encoding_age'] >= self.encoding_ttl:
                    face_location = [current_face_locations[detection_idx]]
                    encodings = face_recognition.face_encodings(
                        rgb_frame,
                        face_location,
                        num_jitters=self.jitter_count,
                        model="small" if self.use_small_model else "large"
                    )

                    if encodings:
                        self.face_trackers[face_id]['encoding'] = encodings[0]
                        self.face_trackers[face_id]['encoding_age'] = 0

                        # Re-identify face
                        self._identify_face(face_id, encodings[0])
                else:
                    self.face_trackers[face_id]['encoding_age'] += 1

            # Create new trackers for unmatched detections
            for idx in unmatched_detections:
                face_location = [current_face_locations[idx]]
                encodings = face_recognition.face_encodings(
                    rgb_frame,
                    face_location,
                    num_jitters=self.jitter_count,
                    model="small" if self.use_small_model else "large"
                )

                if encodings:
                    face_id = self.next_face_id
                    self.next_face_id += 1

                    # Create new tracker
                    self.face_trackers[face_id] = {
                        'bbox': current_face_bboxes[idx],
                        'encoding': encodings[0],
                        'encoding_age': 0,
                        'age': 0,
                        'label': "Unknown",
                        'employee_id': None,
                        'confidence': 0
                    }

                    # Identify the face
                    self._identify_face(face_id, encodings[0])
        else:
            # No existing trackers, create new ones for all detections
            face_encodings = face_recognition.face_encodings(
                rgb_frame,
                current_face_locations,
                num_jitters=self.jitter_count,
                model="small" if self.use_small_model else "large"
            )

            for i, (face_location, face_encoding) in enumerate(zip(current_face_bboxes, face_encodings)):
                face_id = self.next_face_id
                self.next_face_id += 1

                # Create new tracker
                self.face_trackers[face_id] = {
                    'bbox': face_location,
                    'encoding': face_encoding,
                    'encoding_age': 0,
                    'age': 0,
                    'label': "Unknown",
                    'employee_id': None,
                    'confidence': 0
                }

                # Identify the face
                self._identify_face(face_id, face_encoding)

        # Prepare output with current trackers
        for face_id, tracker_data in self.face_trackers.items():
            x, y, w, h = tracker_data['bbox']

            # Log attendance if recognized and cooldown period passed
            if tracker_data['employee_id'] is not None:
                current_time = time.time()
                last_time = self.last_attendance_time.get(tracker_data['employee_id'], 0)

                if current_time - last_time > self.attendance_cooldown:
                    self.last_attendance_time[tracker_data['employee_id']] = current_time

                    # Use app context for database operations
                    if self.app:
                        try:
                            with self.app.app_context():
                                result = self.db_service.log_attendance(tracker_data['employee_id'])

                                # Handle different attendance actions
                                if isinstance(result, dict):
                                    action = result.get('action', '')

                                    if action == 'check-in':
                                        logger.info(f"Checked IN employee ID {tracker_data['employee_id']}")
                                        # Update label to show check-in status
                                        tracker_data['label'] += " [IN]"
                                    elif action == 'check-out':
                                        logger.info(f"Checked OUT employee ID {tracker_data['employee_id']}")
                                        # Update label to show check-out status
                                        hours = result.get('hours', 0)
                                        tracker_data['label'] += f" [OUT: {hours}h]"
                                    elif action == 'update-checkin':
                                        logger.info(f"Updated check-in time for employee ID {tracker_data['employee_id']}")
                                        tracker_data['label'] += " [IN]"
                                    elif action == 'additional-checkin':
                                        logger.info(f"Additional check-in for employee ID {tracker_data['employee_id']}")
                                        tracker_data['label'] += " [IN+]"
                                    elif action == 'skip':
                                        reason = result.get('reason', '')
                                        if reason == 'already-checkout':
                                            tracker_data['label'] += " [OUT]"
                                        else:
                                            tracker_data['label'] += " [IN]"
                                else:
                                    logger.info(f"Logged attendance for employee ID {tracker_data['employee_id']}")
                        except Exception as e:
                            logger.error(f"Failed to log attendance: {e}")

            # Add to detected faces
            detected_faces.append((x, y, w, h, tracker_data['label']))

        return detected_faces

    def _identify_face(self, face_id, face_encoding):
        """
        Identify a face by comparing with known employee profiles
        """
        best_match_confidence = 0
        best_match_id = None
        best_match_name = "Unknown"

        # Compare with known employees
        for employee in self.employee_profiles:
            # Use distance for better matching
            face_distances = face_recognition.face_distance([employee["encoding"]], face_encoding)
            if len(face_distances) > 0:
                current_confidence = 1 - face_distances[0]

                if current_confidence > self.recognition_threshold and current_confidence > best_match_confidence:
                    best_match_confidence = current_confidence
                    best_match_id = employee["id"]
                    best_match_name = employee["name"]

        # Update tracker with identification results
        if best_match_id is not None:
            confidence_text = f" ({int(best_match_confidence*100)}%)" if self.show_recognition_score else ""
            self.face_trackers[face_id]['label'] = f"{best_match_name}{confidence_text}"
            self.face_trackers[face_id]['employee_id'] = best_match_id
            self.face_trackers[face_id]['confidence'] = best_match_confidence
        else:
            self.face_trackers[face_id]['label'] = "Unknown"
            self.face_trackers[face_id]['employee_id'] = None
            self.face_trackers[face_id]['confidence'] = 0

    def _calculate_iou(self, bbox1, bbox2):
        """
        Calculate Intersection over Union between two bounding boxes
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        # Calculate coordinates of intersection
        x_left = max(x1, x2)
        y_top = max(y1, y2)
        x_right = min(x1 + w1, x2 + w2)
        y_bottom = min(y1 + h1, y2 + h2)

        # Check if there is an intersection
        if x_right < x_left or y_bottom < y_top:
            return 0.0

        # Calculate area of intersection
        intersection_area = (x_right - x_left) * (y_bottom - y_top)

        # Calculate area of both bounding boxes
        bbox1_area = w1 * h1
        bbox2_area = w2 * h2

        # Calculate IoU
        iou = intersection_area / float(bbox1_area + bbox2_area - intersection_area)

        return iou

    def generate_frames(self, original_frame):
        """Enhanced frame generation with improved visualization for office environment"""
        with self.face_lock:
            faces = self.faces.copy()

        # Create a copy for drawing
        display_frame = original_frame.copy()

        # Draw faces and information with enhanced styling
        for (x, y, w, h, label) in faces:
            # Determine color based on recognition
            if "Unknown" in label:
                color = (0, 0, 255)  # Red for unknown (BGR format)
                border_thickness = 2
            else:
                color = (0, 255, 0)  # Green for known
                border_thickness = 3  # Thicker border for recognized faces

            # Draw face rectangle with rounded corners
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), color, border_thickness)

            # Calculate text size for better label positioning
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.7, 1)[0]

            # Draw label background with gradient effect
            label_y = max(y - 35, 0)
            label_height = 30

            # Draw label background
            cv2.rectangle(display_frame,
                         (x, label_y),
                         (x + max(w, text_size[0] + 10), label_y + label_height),
                         color, -1)

            # Add a white border for better visibility
            cv2.rectangle(display_frame,
                         (x, label_y),
                         (x + max(w, text_size[0] + 10), label_y + label_height),
                         (255, 255, 255), 1)

            # Draw label text
            cv2.putText(display_frame, label,
                       (x + 5, label_y + 20),
                       cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 1)

            # Draw facial landmarks if enabled and face is known
            if self.show_landmarks and "Unknown" not in label:
                # Convert to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(original_frame, cv2.COLOR_BGR2RGB)

                # Crop to face region with margin
                margin = 20
                x1 = max(0, x - margin)
                y1 = max(0, y - margin)
                x2 = min(rgb_frame.shape[1], x + w + margin)
                y2 = min(rgb_frame.shape[0], y + h + margin)

                face_rgb = rgb_frame[y1:y2, x1:x2]

                if face_rgb.size > 0:  # Check if crop is valid
                    # Process with face mesh
                    results = self.face_mesh.process(face_rgb)

                    if results.multi_face_landmarks:
                        for face_landmarks in results.multi_face_landmarks:
                            # Draw landmarks on the original frame
                            for landmark in face_landmarks.landmark:
                                # Convert normalized coordinates to pixel coordinates
                                lm_x = int(landmark.x * face_rgb.shape[1]) + x1
                                lm_y = int(landmark.y * face_rgb.shape[0]) + y1

                                # Draw small circles for landmarks
                                cv2.circle(display_frame, (lm_x, lm_y), 1, (255, 255, 0), -1)

        # Add system information overlay
        if self.show_fps and self.fps_values:
            avg_fps = sum(self.fps_values) / len(self.fps_values)

            # Create semi-transparent overlay for system info
            info_overlay = display_frame.copy()
            cv2.rectangle(info_overlay, (10, 10), (200, 90), (0, 0, 0), -1)
            cv2.addWeighted(info_overlay, 0.6, display_frame, 0.4, 0, display_frame)

            # Add FPS counter
            cv2.putText(display_frame, f"FPS: {avg_fps:.1f}", (20, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # Add face count
            cv2.putText(display_frame, f"Faces: {len(faces)}", (20, 55),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # Add system status
            cv2.putText(display_frame, "System: Active", (20, 80),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Add timestamp
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(display_frame, current_time,
                   (display_frame.shape[1] - 200, display_frame.shape[0] - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return display_frame
