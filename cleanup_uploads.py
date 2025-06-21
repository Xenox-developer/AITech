#!/usr/bin/env python3
"""
Cron script to clean up old uploads
Add to crontab: 0 2 * * * /path/to/venv/bin/python /path/to/cleanup_uploads.py
"""
import os
import time
import logging
from pathlib import Path
from datetime import datetime

# Configuration
UPLOAD_DIR = Path('uploads')
MAX_AGE_HOURS = 24
LOG_FILE = 'cleanup.log'

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def cleanup_old_files():
    """Remove files older than MAX_AGE_HOURS"""
    if not UPLOAD_DIR.exists():
        logger.warning(f"Upload directory {UPLOAD_DIR} does not exist")
        return
    
    current_time = time.time()
    removed_count = 0
    total_size = 0
    
    logger.info(f"Starting cleanup of files older than {MAX_AGE_HOURS} hours")
    
    for file_path in UPLOAD_DIR.glob('*'):
        # Skip .gitkeep
        if file_path.name == '.gitkeep':
            continue
            
        if file_path.is_file():
            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > (MAX_AGE_HOURS * 3600):
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    removed_count += 1
                    total_size += file_size
                    logger.info(f"Removed: {file_path.name} (age: {file_age/3600:.1f} hours, size: {file_size/1024/1024:.1f} MB)")
            except Exception as e:
                logger.error(f"Error removing {file_path.name}: {str(e)}")
    
    logger.info(f"Cleanup complete. Removed {removed_count} files, freed {total_size/1024/1024:.1f} MB")

if __name__ == "__main__":
    cleanup_old_files()