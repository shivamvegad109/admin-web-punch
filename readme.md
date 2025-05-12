# Face Recognition Attendance System

A modern, web-based attendance tracking system using facial recognition technology. This application allows organizations to automate attendance tracking by recognizing employees through a camera feed.

![Face Recognition System](https://img.shields.io/badge/Face%20Recognition-System-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen)
![Flask](https://img.shields.io/badge/Flask-2.0%2B-lightgrey)
![OpenCV](https://img.shields.io/badge/OpenCV-4.5%2B-red)

## Features

- **Real-time Face Recognition**: Detect and recognize faces in real-time from camera feeds
- **Employee Management**: Add, edit, and remove employees with their facial data
- **Attendance Tracking**: Automatically log attendance when an employee is recognized
- **Admin Dashboard**: View attendance statistics, manage employees, and system settings
- **Reporting**: Generate and export attendance reports
- **Responsive UI**: Modern, mobile-friendly user interface

## System Requirements

- Python 3.8 or higher
- Webcam or IP camera
- 4GB RAM or higher (for optimal face recognition performance)
- Windows, macOS, or Linux operating system

## Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)
- Git (optional)

### Step 1: Clone or Download the Repository

```bash
git clone https://github.com/yourusername/face-recognition-attendance.git
cd face-recognition-attendance
```

Or download and extract the ZIP file.

### Step 2: Create and Activate Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up Environment Variables (Optional)

Create a `.env` file in the project root directory with the following variables:

```
SECRET_KEY=your_secret_key
RTSP_URL=your_camera_url  # Default: http://192.168.1.20:4747/video
UPLOAD_FOLDER=uploads
BATCH_DIRECTORY=employee_images
```

### Step 5: Initialize the Database

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### Step 6: Create Required Directories

```bash
mkdir uploads employee_images
```

## Usage

### Starting the Application

```bash
python run.py
```

The application will start and be accessible at `http://localhost:8000`.

### Main Pages

- **Home Page**: View the live camera feed with face recognition
- **Add Employee**: Register new employees with their facial data
- **Admin Dashboard**: Access comprehensive system management at `/admin`

## Admin Interface

The admin interface provides access to:

1. **Dashboard**: Overview of system statistics
2. **Employees**: Manage employee information
3. **Attendance**: View and export attendance records
4. **Settings**: Configure system parameters

## Camera Configuration

By default, the system tries to connect to an IP camera at `http://192.168.1.20:4747/video`. If unavailable, it falls back to the default webcam.

To use a different camera:
- Update the `RTSP_URL` in the `.env` file
- Or modify the URL in the admin settings page

## Using IP Webcam

For Android devices, you can use the "IP Webcam" app:
1. Install "IP Webcam" from Google Play Store
2. Start the server in the app
3. Set the `RTSP_URL` to the provided URL (usually `http://device-ip:4747/video`)

## Troubleshooting

### Camera Connection Issues

- Ensure the camera URL is correct
- Check if the camera is accessible from your network
- Verify firewall settings allow the connection

### Face Recognition Problems

- Ensure good lighting conditions
- Use clear, front-facing photos for employee registration
- Adjust detection confidence in settings if needed

## Performance Optimization

For better performance:
- Use a dedicated GPU if available
- Adjust frame resolution and processing rate in settings
- Ensure adequate lighting in the camera environment

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Face recognition powered by [face_recognition](https://github.com/ageitgey/face_recognition)
- Video processing with OpenCV
- Web interface built with Flask and Bootstrap

## Contact

For support or inquiries, please contact [your-email@example.com](mailto:your-email@example.com).
