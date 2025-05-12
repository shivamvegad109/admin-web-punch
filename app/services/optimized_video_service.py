import time
import cv2
import threading
import numpy as np
from queue import Queue
from app import logger

class OptimizedVideoService:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, rtsp_url="http://192.168.1.20:4747/video", resolution=(640, 480), fps=15):
        if self._initialized:
            return
            
        self._initialized = True
        self.cap = None
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.frame_queue = Queue(maxsize=10)  # Increased queue size
        self.thread = None
        self.rtsp_url = rtsp_url
        
        # Video settings
        self.resolution = resolution
        self.target_fps = fps
        self.quality = 80  # JPEG quality for streaming
        
        # Performance metrics
        self.actual_fps = 0
        self.dropped_frames = 0
        self.reconnect_count = 0
        
        # Advanced settings
        self.enable_motion_detection = False
        self.motion_threshold = 25
        self.previous_frame = None
        self.motion_detected = False
        self.frame_skip = 2  # Process every nth frame
        self.frame_count = 0

    def start(self):
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logger.info("Optimized video capture started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.cap and self.cap.isOpened():
            self.cap.release()
        logger.info("Video capture stopped")

    def _ensure_capture_open(self):
        if self.cap and self.cap.isOpened():
            return True
        
        try:
            # Try using the default camera (index 0) if RTSP URL fails
            if self.rtsp_url and "http" in self.rtsp_url:
                logger.info(f"Attempting to open RTSP URL: {self.rtsp_url}")
                self.cap = cv2.VideoCapture(self.rtsp_url)
                if not self.cap.isOpened():
                    logger.warning(f"Failed to open RTSP URL, trying default camera")
                    self.cap = cv2.VideoCapture(0)
            else:
                # Use camera index (usually 0 for built-in webcam)
                logger.info("Attempting to open default camera")
                self.cap = cv2.VideoCapture(0)
            
            if self.cap.isOpened():
                # Set camera properties
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
                
                # Additional optimizations
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffering
                
                logger.info(f"Camera opened successfully at {self.resolution[0]}x{self.resolution[1]}, {self.target_fps} FPS")
                return True
            else:
                logger.error("Failed to open camera")
        except Exception as e:
            logger.error(f"Capture initialization failed: {e}")
        
        return False

    def _reconnect(self):
        """Attempt to reconnect to the camera"""
        logger.warning("Reconnecting to camera...")
        if self.cap:
            self.cap.release()
        self.cap = None
        self.reconnect_count += 1
        time.sleep(1)  # Wait before reconnecting

    def _capture_loop(self):
        retry_count = 0
        max_retries = 5
        last_fps_time = time.time()
        frames_captured = 0
        
        while self.running:
            if not self._ensure_capture_open():
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Failed to open camera after {max_retries} attempts")
                    time.sleep(5)  # Wait longer between retries
                    retry_count = 0
                else:
                    logger.warning(f"Retrying camera connection ({retry_count}/{max_retries})")
                    time.sleep(1)
                continue
            
            retry_count = 0  # Reset retry count on successful connection
            
            # Read frame
            ret, new_frame = self.cap.read()
            if not ret:
                logger.warning("Frame read failed")
                self._reconnect()
                continue
            
            # Update FPS calculation
            frames_captured += 1
            current_time = time.time()
            elapsed = current_time - last_fps_time
            
            if elapsed >= 1.0:  # Update FPS every second
                self.actual_fps = frames_captured / elapsed
                frames_captured = 0
                last_fps_time = current_time
            
            # Frame skipping for performance
            self.frame_count += 1
            if self.frame_count % self.frame_skip != 0:
                continue
            
            # Process frame
            try:
                # Resize if needed for performance
                if new_frame.shape[1] != self.resolution[0] or new_frame.shape[0] != self.resolution[1]:
                    new_frame = cv2.resize(new_frame, self.resolution)
                
                # Motion detection (optional)
                if self.enable_motion_detection:
                    self.motion_detected = self._detect_motion(new_frame)
                
                # Store frame with lock
                with self.lock:
                    self.frame = new_frame.copy()
                
                # Convert to RGB for face recognition
                rgb_frame = cv2.cvtColor(new_frame, cv2.COLOR_BGR2RGB)
                
                # Add to queue if not full
                if not self.frame_queue.full():
                    self.frame_queue.put(rgb_frame)
                else:
                    self.dropped_frames += 1
                    
            except Exception as e:
                logger.error(f"Capture processing error: {e}")

    def _detect_motion(self, frame):
        """Simple motion detection"""
        # Convert to grayscale and blur
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # Initialize previous frame if needed
        if self.previous_frame is None:
            self.previous_frame = gray
            return False
        
        # Calculate absolute difference
        frame_delta = cv2.absdiff(self.previous_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        
        # Update previous frame
        self.previous_frame = gray
        
        # Check if motion detected
        return np.sum(thresh) > self.motion_threshold

    def generate_frames(self, face_service):
        """Generate frames for streaming with face recognition overlay"""
        while self.running:
            try:
                with self.lock:
                    if self.frame is None:
                        continue
                    frame_copy = self.frame.copy()
                
                # Apply face recognition overlay
                processed_frame = face_service.generate_frames(frame_copy)
                
                # Add performance metrics
                cv2.putText(processed_frame, f"FPS: {self.actual_fps:.1f}", (10, 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                
                # Encode frame for streaming
                ret, buffer = cv2.imencode('.jpg', processed_frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.quality])
                if not ret:
                    continue
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            except Exception as e:
                logger.error(f"Frame generation error: {e}")
                time.sleep(0.1)  # Prevent tight loop on error
