import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'supersecretkey')
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
    RTSP_URL = os.getenv('RTSP_URL', 'http://192.168.1.20:4747/video')
    USE_POSTGRES = os.getenv("USE_POSTGRES", "False").lower() == "true"
    DB_PATH = os.getenv("DB_PATH", "employees.db")
    BATCH_DIRECTORY = os.getenv("BATCH_DIRECTORY", "employee_images")
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or \
        f'sqlite:///{DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # PostgreSQL configuration (if using)
    PG_DBNAME = os.getenv("PG_DBNAME", "face_recognition")
    PG_USER = os.getenv("PG_USER", "postgres")
    PG_PASSWORD = os.getenv("PG_PASSWORD", "password")
    PG_HOST = os.getenv("PG_HOST", "localhost")
    PG_PORT = os.getenv("PG_PORT", "5432")