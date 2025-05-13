from app import create_app
from waitress import serve
import socket
import logging
from app.services.optimized_video_service import OptimizedVideoService
from app.services.optimized_face_service import OptimizedFaceService
from app.config import Config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_port(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.bind((host, port))
            return True
        except socket.error:
            return False

def main():
    """
    Enhanced main function with improved service initialization for office environments
    """
    logger.info("Starting Face Recognition System for Office Environment")

    # Create Flask application
    app = create_app()

    # Get configuration settings
    rtsp_url = Config.RTSP_URL
    logger.info(f"Using camera source: {rtsp_url if rtsp_url else 'Default Camera'}")

    # Initialize optimized services with settings for office environment
    video_service = OptimizedVideoService(
        rtsp_url=rtsp_url,
        resolution=(1280, 720),  # Higher resolution for better face recognition
        fps=20  # Higher FPS for smoother video
    )

    # Initialize face service with app context
    face_service = OptimizedFaceService(app=app)

    # Start video service first (doesn't need app context)
    logger.info("Starting video capture service...")
    video_service.start()

    # Store services in app config and start face service within app context
    with app.app_context():
        logger.info("Starting face recognition service...")
        # Start face service within app context
        face_service.start(video_service.frame_queue)

        # Store services in app config for access in routes
        app.config['video_service'] = video_service
        app.config['face_service'] = face_service

        # Log system status
        logger.info(f"System initialized with {len(face_service.employee_profiles)} employee profiles")

    # Try multiple ports for web server
    host = '0.0.0.0'  # Listen on all interfaces
    ports = [8000, 8001, 8002, 8080, 5000]  # Try more common ports
    selected_port = None

    # Find available port
    for port in ports:
        if check_port(host, port):
            selected_port = port
            break

    if not selected_port:
        logger.error("No available ports. Exiting.")
        video_service.stop()
        face_service.stop()
        return

    # Start web server
    try:
        logger.info(f"Starting web server on http://{host}:{selected_port}")
        logger.info(f"Admin interface available at http://localhost:{selected_port}/admin")

        # Use more threads for better performance with multiple clients
        serve(app, host=host, port=selected_port, threads=8)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Clean shutdown
        logger.info("Shutting down services...")
        video_service.stop()
        face_service.stop()
        logger.info("System shutdown complete")

if __name__ == "__main__":
    main()
