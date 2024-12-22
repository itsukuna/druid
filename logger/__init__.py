import logging
import logging.config
import os


LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')

os.makedirs(LOG_DIR, exist_ok=True)

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
        'bot_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'bot.log'),
            'formatter': 'standard',
        },
        'database_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'database.log'),
            'formatter': 'standard',
        },
    },
    'loggers': {
        '': { 
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True
        },
        'discord': {
            'handlers': ['console', 'bot_file'],
            'level': 'INFO',
            'propagate': False
        },        
        'mongodb':{
            'handlers':['console','database_file'],
            'level':'INFO',
            'propagate':False
        }
    }
}

def setup_logging():
    logging.config.dictConfig(LOGGING_CONFIG)