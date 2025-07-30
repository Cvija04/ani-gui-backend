"""
Simple configuration manager for Django backend.
Only contains essential settings needed for anime scraping.
"""
import os
from pathlib import Path

class SimpleConfigManager:
    def __init__(self):
        # Use Django's BASE_DIR or current directory
        self.config_dir = Path(__file__).parent.parent / 'cache' 
        self.config_dir.mkdir(exist_ok=True, parents=True)
        
        # Simple hardcoded configuration for backend
        self._config = {
            'SCRAPING': {
                'base_url': 'allmanga.to',
                'api_url': 'https://api.allanime.day',
                'referer': 'https://allmanga.to',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            'DEFAULT': {
                'cache_thumbnails': 'true'
            }
        }
    
    def get(self, section, key, fallback=None):
        """Get configuration value"""
        try:
            return self._config[section][key]
        except KeyError:
            return fallback
    
    def set(self, section, key, value):
        """Set configuration value"""
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = str(value)
