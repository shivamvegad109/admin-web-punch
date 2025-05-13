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

    def __init__(self, rtsp_url="http://192.168.1.20:4747/video", resolution=(1280, 720), fps=20):
        if self._initialized:
            return

        self._initialized = True
        self.cap = None
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.frame_queue = Queue(maxsize=20)  # Increased queue size for smoother processing
        self.thread = None
        self.rtsp_url = rtsp_url

        # Video settings optimized for office cameras
        self.resolution = resolution  # Higher resolution for better face recognition
        self.target_fps = fps  # Higher FPS for smoother video
        self.quality = 90  # Higher JPEG quality for better visualization

        # Camera connection settings
        self.connection_timeout = 10  # Seconds to wait for connection
        self.camera_options = [
            # Try different camera sources in order
            {"source": self.rtsp_url, "type": "rtsp"},
            {"source": 0, "type": "webcam"},  # Default webcam
            {"source": 1, "type": "webcam"},  # External webcam
        ]
        self.current_camera_index = 0

        # Performance metrics
        self.actual_fps = 0
        self.dropped_frames = 0
        self.reconnect_count = 0
        self.last_frame_time = 0
        self.frame_times = []  # For calculating average processing time

        # Advanced settings
        self.enable_motion_detection = False
        self.motion_threshold = 25
        self.previous_frame = None
        self.motion_detected = False
        self.frame_skip = 1  # Process every frame for office environment
        self.frame_count = 0

        # Image enhancement settings
        self.enable_enhancement = True
        self.brightness = 0  # -50 to 50
        self.contrast = 10   # -50 to 50
        self.saturation = 10  # -50 to 50
        self.auto_white_balance = True

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
        """Enhanced camera connection with fallback options for office environments"""
        # If camera is already open and working, return True
        if self.cap and self.cap.isOpened():
            # Check if the camera is still responsive
            ret = self.cap.grab()  # Lightweight check
            if ret:
                return True
            else:
                # Camera is open but not responsive, release it
                self.cap.release()
                self.cap = None
                logger.warning("Camera connection lost, will attempt to reconnect")

        # Try each camera option in sequence
        start_index = self.current_camera_index
        tried_all = False

        while not tried_all:
            camera_option = self.camera_options[self.current_camera_index]
            source_type = camera_option["type"]
            source = camera_option["source"]

            try:
                logger.info(f"Attempting to connect to camera: {source} (type: {source_type})")

                # Create VideoCapture with appropriate source
                self.cap = cv2.VideoCapture(source)

                # Set connection timeout for RTSP streams
                if source_type == "rtsp":
                    # Set RTSP connection parameters
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffering for lower latency

                    # Additional RTSP-specific settings
                    # Use TCP for more reliable connection (instead of default UDP)
                    self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

                    # Set timeout for connection
                    start_time = time.time()
                    connected = False

                    # Try to connect with timeout
                    while time.time() - start_time < self.connection_timeout:
                        if self.cap.isOpened() and self.cap.grab():
                            connected = True
                            break
                        time.sleep(0.5)

                    if not connected:
                        logger.warning(f"RTSP connection timed out after {self.connection_timeout}s")
                        self.cap.release()
                        self.cap = None
                        raise Exception("RTSP connection timeout")

                # Check if camera opened successfully
                if self.cap.isOpened():
                    # Configure camera settings
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                    self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)

                    # Additional optimizations
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffering

                    # Verify camera is working by reading a test frame
                    ret, test_frame = self.cap.read()
                    if not ret or test_frame is None:
                        raise Exception("Camera opened but failed to read test frame")

                    # Get actual camera properties (may differ from requested)
                    actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

                    logger.info(f"Camera connected successfully: {source}")
                    logger.info(f"Resolution: {actual_width}x{actual_height}, FPS: {actual_fps}")

                    # Reset reconnect count on successful connection
                    self.reconnect_count = 0
                    return True
                else:
                    raise Exception("Failed to open camera")

            except Exception as e:
                logger.error(f"Failed to connect to camera {source}: {e}")
                if self.cap:
                    self.cap.release()
                    self.cap = None

                # Try next camera option
                self.current_camera_index = (self.current_camera_index + 1) % len(self.camera_options)
                if self.current_camera_index == start_index:
                    tried_all = True

        # If we've tried all options and failed, log error and return False
        logger.error("Failed to connect to any camera")
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
        """Enhanced capture loop with image quality improvements for office environments"""
        retry_count = 0
        max_retries = 5
        last_fps_time = time.time()
        frames_captured = 0

        while self.running:
            # Ensure camera is connected
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

            # Read frame with timing
            start_time = time.time()
            ret, new_frame = self.cap.read()

            if not ret or new_frame is None:
                logger.warning("Frame read failed")
                self._reconnect()
                continue

            # Update FPS calculation
            frames_captured += 1
            current_time = time.time()
            frame_time = current_time - start_time
            elapsed = current_time - last_fps_time

            # Track frame processing times for performance monitoring
            self.frame_times.append(frame_time)
            if len(self.frame_times) > 30:
                self.frame_times.pop(0)

            if elapsed >= 1.0:  # Update FPS every second
                self.actual_fps = frames_captured / elapsed
                frames_captured = 0
                last_fps_time = current_time

            # Frame skipping for performance if needed
            self.frame_count += 1
            if self.frame_count % self.frame_skip != 0:
                continue

            # Process frame
            try:
                # Resize if needed for consistency
                if new_frame.shape[1] != self.resolution[0] or new_frame.shape[0] != self.resolution[1]:
                    new_frame = cv2.resize(new_frame, self.resolution, interpolation=cv2.INTER_AREA)

                # Apply image enhancements for better face recognition in office lighting
                if self.enable_enhancement:
                    enhanced_frame = self._enhance_image(new_frame)
                else:
                    enhanced_frame = new_frame

                # Motion detection (optional)
                if self.enable_motion_detection:
                    self.motion_detected = self._detect_motion(enhanced_frame)

                # Store frame with lock
                with self.lock:
                    self.frame = enhanced_frame.copy()

                # Convert to RGB for face recognition
                rgb_frame = cv2.cvtColor(enhanced_frame, cv2.COLOR_BGR2RGB)

                # Add to queue if not full
                if not self.frame_queue.full():
                    self.frame_queue.put(rgb_frame)
                else:
                    self.dropped_frames += 1
                    # If we're dropping too many frames, consider increasing skip rate
                    if self.dropped_frames % 30 == 0:
                        logger.warning(f"Dropped {self.dropped_frames} frames, consider adjusting performance settings")

            except Exception as e:
                logger.error(f"Capture processing error: {e}")
                import traceback
                logger.error(traceback.format_exc())

    def _enhance_image(self, frame):
        """Apply image enhancements for better face recognition in office environments"""
        try:
            # Create a copy to avoid modifying the original
            enhanced = frame.copy()

            # Apply brightness and contrast adjustments
            if self.brightness != 0 or self.contrast != 0:
                # Convert to float for processing
                enhanced = enhanced.astype(float)

                # Apply brightness adjustment
                if self.brightness != 0:
                    enhanced += self.brightness

                # Apply contrast adjustment
                if self.contrast != 0:
                    factor = (259 * (self.contrast + 255)) / (255 * (259 - self.contrast))
                    enhanced = factor * (enhanced - 128) + 128

                # Clip values to valid range and convert back to uint8
                enhanced = np.clip(enhanced, 0, 255).astype(np.uint8)

            # Apply color enhancement if needed
            if self.saturation != 0:
                # Convert to HSV for saturation adjustment
                hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV).astype(float)

                # Adjust saturation
                hsv[:, :, 1] *= (1 + self.saturation / 100)
                hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)

                # Convert back to BGR
                enhanced = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

            # Apply auto white balance if enabled
            if self.auto_white_balance:
                # Simple gray world white balance
                b, g, r = cv2.split(enhanced)
                b_avg, g_avg, r_avg = np.mean(b), np.mean(g), np.mean(r)

                # Calculate the average of the three channels
                k = (b_avg + g_avg + r_avg) / 3

                # Scale the channels to balance them
                b = cv2.addWeighted(b, k / b_avg if b_avg > 0 else 1, 0, 0, 0)
                g = cv2.addWeighted(g, k / g_avg if g_avg > 0 else 1, 0, 0, 0)
                r = cv2.addWeighted(r, k / r_avg if r_avg > 0 else 1, 0, 0, 0)

                # Merge the channels back
                enhanced = cv2.merge([b, g, r])

            # Apply noise reduction for better face recognition
            enhanced = cv2.GaussianBlur(enhanced, (3, 3), 0)

            return enhanced

        except Exception as e:
            logger.error(f"Image enhancement error: {e}")
            return frame  # Return original frame if enhancement fails

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
        """Generate enhanced frames for streaming with improved visualization"""
        error_count = 0
        max_errors = 5
        last_frame_time = time.time()

        while self.running:
            try:
                # Calculate time since last frame
                current_time = time.time()
                frame_interval = current_time - last_frame_time

                # Throttle frame rate if needed to prevent browser overload
                if frame_interval < 1.0 / 30:  # Cap at 30 FPS for browser
                    time.sleep(0.01)
                    continue

                # Get current frame with lock
                with self.lock:
                    if self.frame is None:
                        time.sleep(0.01)
                        continue
                    frame_copy = self.frame.copy()

                # Apply face recognition overlay with enhanced visualization
                processed_frame = face_service.generate_frames(frame_copy)

                # Add system status overlay
                self._add_system_overlay(processed_frame)

                # Update last frame time
                last_frame_time = current_time

                # Encode frame for streaming with optimized quality
                # Use higher quality for office environment
                encoding_params = [
                    int(cv2.IMWRITE_JPEG_QUALITY), self.quality,
                    int(cv2.IMWRITE_JPEG_OPTIMIZE), 1
                ]

                ret, buffer = cv2.imencode('.jpg', processed_frame, encoding_params)
                if not ret:
                    logger.warning("Frame encoding failed")
                    continue

                # Reset error count on successful frame
                error_count = 0

                # Yield frame for streaming
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            except Exception as e:
                error_count += 1
                logger.error(f"Frame generation error: {e}")

                if error_count > max_errors:
                    logger.error(f"Too many errors ({error_count}), resetting video service")
                    self._reconnect()
                    error_count = 0

                time.sleep(0.1)  # Prevent tight loop on error

    def _add_system_overlay(self, frame):
        """Add system status overlay to frame"""
        # Calculate average processing time
        avg_processing_time = sum(self.frame_times) / len(self.frame_times) if self.frame_times else 0

        # Create semi-transparent overlay for system info
        h, w = frame.shape[:2]
        overlay = frame.copy()

        # Draw background for system info
        cv2.rectangle(overlay, (w-220, 10), (w-10, 120), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame, dst=frame[10:120, w-220:w-10])

        # Add system information
        cv2.putText(frame, f"FPS: {self.actual_fps:.1f}", (w-210, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        cv2.putText(frame, f"Frame Time: {avg_processing_time*1000:.1f}ms", (w-210, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        cv2.putText(frame, f"Resolution: {self.resolution[0]}x{self.resolution[1]}", (w-210, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # Add camera status
        status_color = (0, 255, 0) if self.cap and self.cap.isOpened() else (0, 0, 255)
        cv2.putText(frame, "Camera: Connected" if (self.cap and self.cap.isOpened()) else "Camera: Disconnected",
                   (w-210, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 1)

        # Add dropped frames info
        if self.dropped_frames > 0:
            cv2.putText(frame, f"Dropped: {self.dropped_frames}", (w-210, 110),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)
