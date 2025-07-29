import configparser
import os
from pathlib import Path
import json
import time
from datetime import datetime

class ConfigManagerMobile:
    def __init__(self):
        # Use app-specific directory for mobile
        if os.name == 'nt':  # Windows
            self.config_dir = Path.home() / '.ani-gui-mobile'
        else:  # Android/Linux
            self.config_dir = Path('/storage/emulated/0/ani-gui-mobile')
            if not self.config_dir.exists():
                self.config_dir = Path.home() / '.ani-gui-mobile'
        
        self.config_file = self.config_dir / 'config.ini'
        self.history_file = self.config_dir / 'history.json'
        self.favorites_file = self.config_dir / 'favorites.json'
        self.watch_later_file = self.config_dir / 'watch_later.json'
        self.last_watched_file = self.config_dir / 'last_watched.json'
        
        # Create directories if they don't exist
        self.config_dir.mkdir(exist_ok=True, parents=True)
        
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self):
        """Load configuration from file or create default"""
        if self.config_file.exists():
            try:
                self.config.read(self.config_file)
            except Exception as e:
                print(f"Error loading config: {e}")
                self.create_default_config()
        else:
            self.create_default_config()
    
    def create_default_config(self):
        """Create default configuration for mobile"""
        self.config['DEFAULT'] = {
            'theme': 'dark',
            'quality': 'best',
            'player': 'external',  # Default to external player on mobile
            'auto_play_next': 'false',
            'remember_position': 'true',
            'volume': '70',
            'grid_columns': '2',  # Mobile-friendly grid
            'cache_thumbnails': 'true'
        }
        
        self.config['APPEARANCE'] = {
            'title': 'Ani-GUI Mobile',
            'font_size': '14',
            'card_height': '350',
            'primary_color': 'Purple'
        }
        
        self.config['SCRAPING'] = {
            'base_url': 'allmanga.to',
            'api_url': 'https://api.allanime.day',
            'referer': 'https://allmanga.to',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        self.config['MOBILE'] = {
            'swipe_sensitivity': '0.2',
            'haptic_feedback': 'true',
            'orientation_lock': 'portrait',
            'keep_screen_on': 'true'
        }
        
        self.save_config()
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                self.config.write(f)
            print(f"[CONFIG] Saved to {self.config_file}")
        except Exception as e:
            print(f"[CONFIG ERROR] Failed to save config: {e}")
    
    def get(self, section, key, fallback=None):
        """Get configuration value"""
        return self.config.get(section, key, fallback=fallback)
    
    def set(self, section, key, value):
        """Set configuration value"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = str(value)
        self.save_config()
    
    def get_history(self):
        """Get watch history"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    # Sort by timestamp (most recent first)
                    def parse_timestamp(entry):
                        try:
                            timestamp_str = entry.get('timestamp', '00:00 01/01/1970')
                            return datetime.strptime(timestamp_str, '%H:%M %d/%m/%Y')
                        except:
                            return datetime.min
                    
                    history.sort(key=parse_timestamp, reverse=True)
                    return history
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []
    
    def add_to_history(self, anime_id, title, episode, url, timestamp=None, position=0, total_duration=0):
        """Add entry to watch history"""
        if timestamp is None:
            timestamp = int(time.time())
            formatted_time = time.strftime("%H:%M %d/%m/%Y", time.localtime(timestamp))
        
        entry = {
            'anime_id': anime_id,
            'title': title,
            'episode': episode,
            'timestamp': formatted_time,
            'url': url,
            'position': position,
            'total_duration': total_duration,
            'completed': position >= 0 and total_duration > 0 and (position / total_duration) >= 0.9
        }
        
        history = self.get_history()
        
        # Remove duplicate entries for same anime/episode
        history = [h for h in history if not (
            h.get('anime_id') == anime_id and 
            str(h.get('episode')) == str(episode)
        )]
        
        history.append(entry)
        
        # Keep only last 200 entries to save space on mobile
        history = history[-200:]
        
        # Update last watched separately
        self.update_last_watched(entry)
        
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")
    
    def update_last_watched(self, entry):
        """Update or create the last watched entry"""
        try:
            with open(self.last_watched_file, 'w', encoding='utf-8') as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to update last watched: {e}")
    
    def get_last_watched(self):
        """Get the last watched entry"""
        try:
            if self.last_watched_file.exists():
                with open(self.last_watched_file, 'r', encoding='utf-8') as f:
                    entry = json.load(f)
                    # Only return if not completed
                    if not entry.get('completed', False):
                        return entry
        except Exception as e:
            print(f"Failed to get last watched: {e}")
        return None
    
    def get_resume_position(self, anime_id, episode):
        """Get resume position for specific anime episode"""
        history = self.get_history()
        for entry in reversed(history):  # Start from most recent
            if (entry.get('anime_id') == anime_id and 
                str(entry.get('episode')) == str(episode) and 
                not entry.get('completed', False)):
                return entry.get('position', 0)
        return 0
    
    def update_watch_position(self, anime_id, title, episode, url, position, total_duration):
        """Update watch position for episode"""
        completed = (position >= total_duration * 0.9) if total_duration > 0 else False
        
        self.add_to_history(anime_id, title, episode, url, position=position, total_duration=total_duration)
        
        if not completed:
            last_watched_entry = {
                'anime_id': anime_id,
                'title': title,
                'episode': episode,
                'timestamp': time.strftime("%H:%M %d/%m/%Y"),
                'url': url,
                'position': position,
                'total_duration': total_duration,
                'completed': False
            }
            self.update_last_watched(last_watched_entry)
        else:
            # Clear last watched if episode is completed
            self.clear_last_watched_if_matches(anime_id, episode)
    
    def clear_last_watched_if_matches(self, anime_id, episode):
        """Clear last watched if it matches the given anime and episode"""
        try:
            current = self.get_last_watched()
            if (current and 
                current.get('anime_id') == anime_id and 
                str(current.get('episode')) == str(episode)):
                if self.last_watched_file.exists():
                    self.last_watched_file.unlink()
        except Exception as e:
            print(f"Failed to clear last watched: {e}")
    
    def add_to_favorites(self, anime_id, title, thumbnail=''):
        """Add anime to favorites"""
        favorites = self.get_favorites()
        
        # Check if already in favorites
        for fav in favorites:
            if fav.get('anime_id') == anime_id:
                return  # Already in favorites
        
        entry = {
            'anime_id': anime_id,
            'title': title,
            'thumbnail': thumbnail,
            'added_time': time.strftime("%H:%M %d/%m/%Y")
        }
        
        favorites.append(entry)
        
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(favorites, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving favorites: {e}")
    
    def remove_from_favorites(self, anime_id):
        """Remove anime from favorites"""
        favorites = self.get_favorites()
        favorites = [fav for fav in favorites if fav.get('anime_id') != anime_id]
        
        try:
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(favorites, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving favorites: {e}")
    
    def is_favorite(self, anime_id):
        """Check if anime is in favorites"""
        favorites = self.get_favorites()
        return any(fav.get('anime_id') == anime_id for fav in favorites)
    
    def get_favorites(self):
        """Get all favorites"""
        if self.favorites_file.exists():
            try:
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []
    
    def add_to_watch_later(self, anime_id, title, thumbnail=''):
        """Add anime to watch later list"""
        watch_later = self.get_watch_later()
        
        # Check if already in watch later
        for item in watch_later:
            if item.get('anime_id') == anime_id:
                return  # Already in watch later
        
        entry = {
            'anime_id': anime_id,
            'title': title,
            'thumbnail': thumbnail,
            'added_time': time.strftime("%H:%M %d/%m/%Y")
        }
        
        watch_later.append(entry)
        
        try:
            with open(self.watch_later_file, 'w', encoding='utf-8') as f:
                json.dump(watch_later, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving watch later: {e}")
    
    def remove_from_watch_later(self, anime_id):
        """Remove anime from watch later list"""
        watch_later = self.get_watch_later()
        watch_later = [item for item in watch_later if item.get('anime_id') != anime_id]
        
        try:
            with open(self.watch_later_file, 'w', encoding='utf-8') as f:
                json.dump(watch_later, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving watch later: {e}")
    
    def is_watch_later(self, anime_id):
        """Check if anime is in watch later list"""
        watch_later = self.get_watch_later()
        return any(item.get('anime_id') == anime_id for item in watch_later)
    
    def get_watch_later(self):
        """Get all watch later items"""
        if self.watch_later_file.exists():
            try:
                with open(self.watch_later_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []
    
    def format_time_position(self, seconds):
        """Format time position for display"""
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"
    
    def get_cache_stats(self):
        """Get cache statistics for mobile optimization"""
        try:
            history_size = len(self.get_history())
            favorites_size = len(self.get_favorites())
            watch_later_size = len(self.get_watch_later())
            
            config_dir_size = sum(
                f.stat().st_size for f in self.config_dir.rglob('*') if f.is_file()
            )
            
            return {
                'history_count': history_size,
                'favorites_count': favorites_size,
                'watch_later_count': watch_later_size,
                'cache_size_mb': round(config_dir_size / (1024 * 1024), 2),
                'config_dir': str(self.config_dir)
            }
        except Exception as e:
            print(f"Error getting cache stats: {e}")
            return {}
    
    def cleanup_cache(self):
        """Clean up cache for mobile storage optimization"""
        try:
            # Keep only last 100 history entries
            history = self.get_history()
            if len(history) > 100:
                history = history[-100:]
                with open(self.history_file, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
            
            print("Cache cleanup completed")
            return True
        except Exception as e:
            print(f"Error during cache cleanup: {e}")
            return False
