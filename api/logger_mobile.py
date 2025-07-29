import logging
import os
from pathlib import Path
from datetime import datetime
import json

class MobileLogger:
    def __init__(self, name, level="INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Create mobile-friendly log directory
        if os.name == 'nt':  # Windows
            self.log_dir = Path.home() / '.ani-gui-mobile' / 'logs'
        else:  # Android/Linux
            self.log_dir = Path('/storage/emulated/0/ani-gui-mobile/logs')
            if not self.log_dir.exists():
                self.log_dir = Path.home() / '.ani-gui-mobile' / 'logs'
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Mobile-optimized log file (smaller, rotated more frequently)
        log_file = self.log_dir / f"ani-gui-mobile-{datetime.now().strftime('%Y%m%d')}.log"
        
        # File handler with mobile-friendly formatting
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler for debugging
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '[%(levelname)s] %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Keep log files small for mobile (max 5 files, 1MB each)
        self.cleanup_old_logs()
    
    def cleanup_old_logs(self):
        """Clean up old log files to save mobile storage"""
        try:
            log_files = list(self.log_dir.glob("ani-gui-mobile-*.log"))
            log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Keep only the latest 5 log files
            for old_log in log_files[5:]:
                try:
                    old_log.unlink()
                except:
                    pass
                    
            # Check file sizes and rotate if too large
            for log_file in log_files[:5]:
                if log_file.stat().st_size > 1024 * 1024:  # 1MB limit
                    # Create new log file
                    new_name = f"ani-gui-mobile-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
                    log_file.rename(self.log_dir / new_name)
                    break
                    
        except Exception as e:
            print(f"Error cleaning up logs: {e}")
    
    def info(self, message):
        """Log info message"""
        self.logger.info(message)
    
    def error(self, message, exception=None):
        """Log error message with optional exception"""
        if exception:
            self.logger.error(f"{message}: {str(exception)}")
        else:
            self.logger.error(message)
    
    def warning(self, message):
        """Log warning message"""
        self.logger.warning(message)
    
    def debug(self, message):
        """Log debug message"""
        self.logger.debug(message)
    
    def log_app_start(self):
        """Log application startup"""
        self.info("=" * 50)
        self.info("Ani-GUI Mobile Application Started")
        self.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.info(f"Platform: {os.name}")
        self.info("=" * 50)
    
    def log_performance(self, operation, duration):
        """Log performance metrics"""
        self.debug(f"PERF: {operation} took {duration:.2f}s")
    
    def log_user_action(self, action, details=None):
        """Log user actions for analytics"""
        message = f"USER: {action}"
        if details:
            message += f" - {details}"
        self.info(message)
    
    def log_network_request(self, url, status_code, duration=None):
        """Log network requests"""
        message = f"NET: {url} -> {status_code}"
        if duration:
            message += f" ({duration:.2f}s)"
        self.debug(message)
    
    def log_cache_operation(self, operation, item, success=True):
        """Log cache operations"""
        status = "SUCCESS" if success else "FAILED"
        self.debug(f"CACHE: {operation} {item} - {status}")
    
    def get_log_stats(self):
        """Get log statistics for mobile optimization"""
        try:
            log_files = list(self.log_dir.glob("*.log"))
            total_size = sum(f.stat().st_size for f in log_files)
            
            return {
                'log_count': len(log_files),
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'log_dir': str(self.log_dir),
                'latest_log': max(log_files, key=lambda x: x.stat().st_mtime).name if log_files else None
            }
        except Exception as e:
            return {'error': str(e)}

# Global logger instance
_logger_instance = None

def get_logger(level="INFO"):
    """Get or create global logger instance"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = MobileLogger("AniGUIMobile", level)
    return _logger_instance

def log_startup_info():
    """Log startup information"""
    logger = get_logger()
    logger.log_app_start()

class LogContext:
    """Context manager for logging operations"""
    def __init__(self, operation_name):
        self.operation_name = operation_name
        self.logger = get_logger()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"START: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        if exc_type:
            self.logger.error(f"FAILED: {self.operation_name} - {exc_val}")
        else:
            self.logger.debug(f"COMPLETE: {self.operation_name} ({duration:.2f}s)")

# Convenience functions
def log_info(message):
    get_logger().info(message)

def log_error(message, exception=None):
    get_logger().error(message, exception)

def log_warning(message):
    get_logger().warning(message)

def log_debug(message):
    get_logger().debug(message)

def log_user_action(action, details=None):
    get_logger().log_user_action(action, details)

def log_performance(operation, duration):
    get_logger().log_performance(operation, duration)
