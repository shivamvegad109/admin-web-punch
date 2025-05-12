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
    app = create_app()

    # Initialize optimized services
    video_service = OptimizedVideoService(Config.RTSP_URL, resolution=(640, 480), fps=15)
    face_service = OptimizedFaceService(app=app)

    # Start video service first (doesn't need app context)
    video_service.start()

    # Store services in app config and start face service within app context
    with app.app_context():
        # Start face service within app context
        face_service.start(video_service.frame_queue)

        # Store services in app config for access in routes
        app.config['video_service'] = video_service
        app.config['face_service'] = face_service

    # Try multiple ports
    host = '0.0.0.0'
    ports = [8000, 8001, 8002]
    selected_port = None

    for port in ports:
        if check_port(host, port):
            selected_port = port
            break

    if not selected_port:
        logger.error("No available ports. Exiting.")
        return

    try:
        logger.info(f"Starting server on port {selected_port}...")
        serve(app, host=host, port=selected_port, threads=4)
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        video_service.stop()
        face_service.stop()

if __name__ == "__main__":
    main()
