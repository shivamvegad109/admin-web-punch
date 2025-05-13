from app import db, logger
from app.models import Notification, Employee
from datetime import datetime, timedelta, timezone
from sqlalchemy import desc

class NotificationService:
    """Service for managing notifications in the system"""
    
    # Notification types
    TYPE_INFO = 'info'
    TYPE_SUCCESS = 'success'
    TYPE_WARNING = 'warning'
    TYPE_DANGER = 'danger'
    
    # Icon mapping
    ICON_MAP = {
        TYPE_INFO: 'fa-info-circle',
        TYPE_SUCCESS: 'fa-check-circle',
        TYPE_WARNING: 'fa-exclamation-triangle',
        TYPE_DANGER: 'fa-exclamation-circle',
        'user': 'fa-user',
        'attendance': 'fa-clock',
        'system': 'fa-cog',
    }
    
    def __init__(self, enabled=True):
        """Initialize the notification service
        
        Args:
            enabled (bool): Whether notifications are enabled
        """
        self.enabled = enabled
    
    def create_notification(self, message, type=TYPE_INFO, icon=None, employee_id=None):
        """Create a new notification
        
        Args:
            message (str): The notification message
            type (str): Notification type (info, success, warning, danger)
            icon (str): FontAwesome icon class (without 'fa-' prefix)
            employee_id (int): Related employee ID, if any
            
        Returns:
            Notification: The created notification object or None if disabled
        """
        if not self.enabled:
            logger.info(f"Notification not created (disabled): {message}")
            return None
            
        # Set icon based on type if not provided
        if not icon and type in self.ICON_MAP:
            icon = self.ICON_MAP[type]
        elif icon and not icon.startswith('fa-'):
            icon = f"fa-{icon}"
            
        try:
            notification = Notification(
                message=message,
                type=type,
                icon=icon,
                employee_id=employee_id
            )
            
            db.session.add(notification)
            db.session.commit()
            
            logger.info(f"Notification created: {message}")
            return notification
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating notification: {e}")
            return None
    
    def get_notifications(self, limit=10, include_read=False, employee_id=None):
        """Get recent notifications
        
        Args:
            limit (int): Maximum number of notifications to return
            include_read (bool): Whether to include read notifications
            employee_id (int): Filter by employee ID
            
        Returns:
            list: List of notification objects
        """
        query = Notification.query
        
        # Filter by read status if needed
        if not include_read:
            query = query.filter_by(is_read=False)
            
        # Filter by employee if needed
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
            
        # Order by creation time (newest first)
        query = query.order_by(desc(Notification.created_at))
        
        # Limit results
        if limit:
            query = query.limit(limit)
            
        return query.all()
    
    def mark_as_read(self, notification_id):
        """Mark a notification as read
        
        Args:
            notification_id (int): The notification ID
            
        Returns:
            bool: Success status
        """
        try:
            notification = Notification.query.get(notification_id)
            if notification:
                notification.is_read = True
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marking notification as read: {e}")
            return False
    
    def mark_all_as_read(self, employee_id=None):
        """Mark all notifications as read
        
        Args:
            employee_id (int): Filter by employee ID
            
        Returns:
            int: Number of notifications marked as read
        """
        try:
            query = Notification.query.filter_by(is_read=False)
            
            if employee_id:
                query = query.filter_by(employee_id=employee_id)
                
            count = query.count()
            
            if count > 0:
                query.update({Notification.is_read: True})
                db.session.commit()
                
            return count
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error marking all notifications as read: {e}")
            return 0
    
    def delete_old_notifications(self, days=30):
        """Delete notifications older than specified days
        
        Args:
            days (int): Delete notifications older than this many days
            
        Returns:
            int: Number of notifications deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            # Find notifications older than cutoff date
            old_notifications = Notification.query.filter(
                Notification.created_at < cutoff_date
            )
            
            count = old_notifications.count()
            
            if count > 0:
                old_notifications.delete()
                db.session.commit()
                
            return count
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting old notifications: {e}")
            return 0
