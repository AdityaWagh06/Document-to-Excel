import logging
from logging.handlers import RotatingFileHandler
import os

def configure_logger():
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # General App Log Handler
    app_log_path = os.path.join(log_dir, 'app.log')
    app_handler = RotatingFileHandler(app_log_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    app_handler.setFormatter(formatter)
    app_handler.setLevel(logging.INFO)
    logger.addHandler(app_handler)

    # Error Log Handler
    error_log_path = os.path.join(log_dir, 'error.log')
    error_handler = RotatingFileHandler(error_log_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.WARNING)
    logger.addHandler(error_handler)
