# Check-in/Check-out Functionality

This document explains the new Check-in/Check-out functionality added to the Face Recognition system.

## Overview

The system now supports proper Check-in and Check-out tracking for employees, allowing you to:

1. Track when employees arrive (Check-in)
2. Track when employees leave (Check-out)
3. Calculate work hours automatically
4. Configure work hour settings

## How It Works

### Automatic Check-in/Check-out

When the system recognizes an employee's face:

1. **First recognition of the day**: The system logs a Check-in
2. **Later recognition**: If enough time has passed since Check-in (configurable), the system logs a Check-out
3. **After Check-out**: If the employee is recognized again later, a new Check-in is recorded

### Visual Indicators

The system shows the employee's check-in/check-out status directly on the video feed:

- `[IN]`: Employee is checked in
- `[OUT: Xh]`: Employee has checked out, with X hours worked
- `[IN+]`: Employee has checked in again after previously checking out

### Work Hours Calculation

Work hours are automatically calculated when an employee checks out, based on the time between check-in and check-out.

## Configuration

You can configure the check-in/check-out behavior in the Admin Settings page:

1. **Work Start Hour**: Default start time for the workday (e.g., 9:00 AM)
2. **Work End Hour**: Default end time for the workday (e.g., 5:00 PM)
3. **Minimum Hours**: Minimum time required between check-in and check-out (prevents accidental check-outs)
4. **Attendance Cooldown**: Minimum time between attendance logs for the same person
5. **Auto Check-out**: Option to automatically check out employees at the end of the workday

## Reports

The Attendance page now shows:

- Check-in time
- Check-out time
- Work status (Checked In, Checked Out)
- Work hours

The Dashboard shows:

- Currently checked-in employees
- Checked-out employees
- Total work hours for the day
- Weekly attendance and work hour charts

## Database Migration

If you're upgrading from a previous version, you need to run the database migration script:

```
python migrations/add_checkin_checkout.py
```

This will update your existing attendance records to the new format.

## Best Practices

1. **Office Camera Placement**: Position cameras at entry/exit points to capture both check-ins and check-outs
2. **Work Hour Settings**: Configure work hours to match your office schedule
3. **Regular Monitoring**: Check the attendance reports regularly to ensure accurate tracking

## Troubleshooting

- **Missing Check-outs**: If employees forget to check out, you can manually update their records in the admin interface
- **Incorrect Work Hours**: Verify the minimum hours setting is appropriate for your office
- **Multiple Check-ins**: If an employee has multiple check-ins on the same day, the system tracks each session separately

For any issues, please contact system support.
