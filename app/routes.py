from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, current_app
from app.services.db_service import DatabaseService
import os
from werkzeug.utils import secure_filename

main_bp = Blueprint('main', __name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/video_feed')
def video_feed():
    video_service = current_app.config.get('video_service')
    face_service = current_app.config.get('face_service')
    if not video_service or not face_service:
        return "Services not initialized", 500
    return Response(video_service.generate_frames(face_service),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@main_bp.route('/upload', methods=['GET', 'POST'])
def upload_employee():
    if request.method == 'POST':
        name = request.form.get('name')
        position = request.form.get('position', '')
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')

        if 'file' not in request.files or not name:
            flash('Name and file are required.', 'danger')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            # Create a database service instance
            db_service = DatabaseService()
            if db_service.add_employee(name, file_path, position, email, phone):
                flash(f'Employee {name} added successfully.', 'success')
            else:
                flash(f'Failed to add employee {name}. No face detected.', 'danger')

            return redirect(url_for('main.upload_employee'))

        flash('Invalid file type. Allowed: jpg, jpeg, png.', 'danger')
        return redirect(request.url)

    return render_template('upload.html')
