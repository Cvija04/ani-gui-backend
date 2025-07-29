import requests
import re
import json
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlencode, quote
import time
from datetime import datetime, timedelta
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from .logger_mobile import get_logger

class EnhancedAnimeScraperMobile:
    def __init__(self, config_manager):
        self.config = config_manager
        self.session = requests.Session()
        
        # Enhanced headers to bypass Cloudflare protection
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 500ms between requests
        
        self.base_url = self.config.get('SCRAPING', 'base_url')
        self.api_url = self.config.get('SCRAPING', 'api_url')
        self.referer = self.config.get('SCRAPING', 'referer')
        
        # Initialize logger
        self.logger = get_logger("INFO")
        
        # Initialize original scraper for episode counting like Windows version
        try:
            from .scraper import AnimeScraper
            self.original_scraper = AnimeScraper(config_manager)
        except ImportError:
            print("Warning: Original scraper not available. Episode counting may be inaccurate.")
            self.original_scraper = None
        
        # Mobile-optimized settings
        self.session.timeout = 10  # Shorter timeout for mobile
        self.max_concurrent_requests = 3  # Fewer concurrent requests on mobile
        self.cache_enabled = self.config.get('DEFAULT', 'cache_thumbnails', fallback='true').lower() == 'true'
        
        # Cache for storing results
        self.cache = {}
        self.cache_expiry = {}
        
        # Data cache directory
        self.cache_dir = self.config.config_dir / 'data_cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def cache_data(self, filename, data):
        """Cache data to a JSON file with timestamp"""
        if not self.cache_enabled:
            return
            
        try:
            cache_file = self.cache_dir / filename
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': time.time(),
                    'data': data
                }, f, ensure_ascii=False)
        except Exception as e:
            print(f"Cache save error: {e}")
    
    def load_cached_data(self, filename, max_age_sec=43200):  # 12 hours for mobile
        """Load data from cache if not expired"""
        if not self.cache_enabled:
            return None
            
        try:
            cache_file = self.cache_dir / filename
            if not cache_file.exists():
                return None
                
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                
            # Check if cache is still valid
            if time.time() - cached.get('timestamp', 0) < max_age_sec:
                return cached.get('data', [])
            else:
                return None
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            return None
    
    def make_api_request(self, url, headers=None, timeout=10):
        """Make API request with mobile optimizations and rate limiting"""
        try:
            # Rate limiting
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                time.sleep(sleep_time)
            
            if headers:
                self.session.headers.update(headers)
            
            response = self.session.get(url, timeout=timeout)
            self.last_request_time = time.time()
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            raise
    
    def search_anime(self, query: str, limit: int = 20) -> List[Dict]:
        """Search anime using original scraper logic for AllAnime API"""
        if not query or not query.strip():
            return []
        
        try:
            # Using original scraper logic from Windows application that works
            results = self.original_scraper.search_anime(query, limit)
            
            if not results:
                print(f"DEBUG: Search failed for '{query}'")
                return []
            
            return results
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def get_episodes_list(self, anime_id: str, anime_title: str = None) -> List[str]:
        """Get list of available episodes for an anime using original scraper"""
        try:
            return self.original_scraper.get_episodes_list(anime_id)
        except Exception as e:
            print(f"Episode list error for {anime_id}: {e}")
            return []
    
    def get_trending_anime(self, limit: int = 20, time_period: str = 'week') -> List[Dict]:
        """Get trending anime based on popularity and recent activity with caching"""
        try:
            # Check cache first
            cache_filename = f'trending_{time_period}_{limit}.json'
            cached_results = self.load_cached_data(cache_filename, max_age_sec=3600)  # 1 hour
            if cached_results:
                return cached_results
            
            trending_gql = '''
            query($limit: Int, $page: Int, $sort: [MediaSort]) {
                Page(page: $page, perPage: $limit) {
                    media(sort: $sort, type: ANIME) {
                        id
                        title { romaji english }
                        episodes
                        coverImage { large }
                        description
                        status
                        genres
                        averageScore
                        popularity
                        trending
                        startDate { year month day }
                        studios { nodes { name } }
                        tags { name }
                    }
                }
            }
            '''
            
            # Determine sort order based on time period
            sort_options = {
                'day': ['TRENDING_DESC', 'POPULARITY_DESC'],
                'week': ['TRENDING_DESC', 'SCORE_DESC'],
                'month': ['POPULARITY_DESC', 'SCORE_DESC'],
                'all_time': ['POPULARITY_DESC', 'SCORE_DESC']
            }
            
            sort_order = sort_options.get(time_period, ['TRENDING_DESC'])
            
            variables = {
                "limit": limit,
                "page": 1,
                "sort": sort_order
            }
            
            # Rate limiting for AniList API
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                time.sleep(sleep_time)
            
            # Using AniList API for trending data with proper headers
            # Use direct requests instead of session to avoid conflicts
            import requests as direct_requests
            response = direct_requests.post(
                'https://graphql.anilist.co',
                json={
                    'query': trending_gql,
                    'variables': variables
                },
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for media in data.get('data', {}).get('Page', {}).get('media', []):
                    # Try to find corresponding AllAnime ID (with rate limiting)
                    anime_title = media.get('title', {}).get('romaji', '') or media.get('title', {}).get('english', '')
                    
                    # Add small delay between AllAnime searches to avoid rate limiting
                    time.sleep(0.2)
                    allanime_id = self._find_allanime_id(anime_title)
                    
                    anime_info = {
                        'id': allanime_id or str(media.get('id')),  # Use AllAnime ID if found, otherwise AniList ID
                        'anilist_id': str(media.get('id')),  # Store original AniList ID
                        'title': anime_title,
                        'episodes': media.get('episodes', 0),
                        'thumbnail': media.get('coverImage', {}).get('large', ''),
                        'description': media.get('description', ''),
                        'status': media.get('status'),
                        'genres': media.get('genres', []),
                        'score': media.get('averageScore'),
                        'popularity': media.get('popularity'),
                        'trending': media.get('trending'),
                        'studios': [studio.get('name') for studio in media.get('studios', {}).get('nodes', [])],
                        'tags': [tag.get('name') for tag in media.get('tags', [])],
                        'start_date': media.get('startDate', {}),
                        'type': 'TV',
                        'year': media.get('startDate', {}).get('year')
                    }
                    results.append(anime_info)
                
                # Cache the results
                self.cache_data(cache_filename, results)
                return results
            
        except Exception as e:
            self.logger.error(f"Trending anime error: {e}")
            return []
        
        return []
    
    def get_seasonal_anime(self, year: int = None, season: str = None) -> List[Dict]:
        """Get seasonal anime releases"""
        try:
            from datetime import datetime
            import requests as direct_requests
            
            current_date = datetime.now()
            if not year:
                year = current_date.year
            if not season:
                season = self._get_current_season()
            
            # Check cache first
            cache_key = f"seasonal_{year}_{season}.json"
            cached_results = self.load_cached_data(cache_key, max_age_sec=7200)  # 2 hours
            if cached_results:
                return cached_results
            
            seasonal_gql = '''
            query($year: Int, $season: MediaSeason, $page: Int, $perPage: Int) {
                Page(page: $page, perPage: $perPage) {
                    media(season: $season, seasonYear: $year, type: ANIME, sort: POPULARITY_DESC) {
                        id
                        title { romaji english }
                        episodes
                        coverImage { large }
                        description
                        status
                        genres
                        averageScore
                        popularity
                        startDate { year month day }
                        studios { nodes { name } }
                        tags { name }
                        airingSchedule { nodes { airingAt episode } }
                    }
                }
            }
            '''
            
            variables = {
                "year": year,
                "season": season.upper(),
                "page": 1,
                "perPage": 30
            }
            
            # Rate limiting for AniList API
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                time.sleep(sleep_time)
            
            # Use direct requests instead of session to avoid conflicts
            response = direct_requests.post(
                'https://graphql.anilist.co',
                json={
                    'query': seasonal_gql,
                    'variables': variables
                },
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for media in data.get('data', {}).get('Page', {}).get('media', []):
                    anime_title = media.get('title', {}).get('romaji', '') or media.get('title', {}).get('english', '')
                    
                    # Add small delay between AllAnime searches
                    time.sleep(0.2)
                    allanime_id = self._find_allanime_id(anime_title)
                    
                    anime_info = {
                        'id': allanime_id or str(media.get('id')),
                        'anilist_id': str(media.get('id')),
                        'title': anime_title,
                        'episodes': media.get('episodes', 0) or 'Unknown',
                        'thumbnail': media.get('coverImage', {}).get('large', ''),
                        'description': media.get('description', ''),
                        'status': media.get('status'),
                        'genres': media.get('genres', []),
                        'score': media.get('averageScore', 0),
                        'popularity': media.get('popularity'),
                        'studios': [studio.get('name') for studio in media.get('studios', {}).get('nodes', [])],
                        'tags': [tag.get('name') for tag in media.get('tags', [])],
                        'start_date': media.get('startDate', {}),
                        'type': 'TV',
                        'year': year,
                        'season': season
                    }
                    results.append(anime_info)
                
                # Cache and return results
                self.cache_data(cache_key, results)
                return results
            
        except Exception as e:
            self.logger.error(f"Seasonal anime error: {e}")
            return []
        
        return []
    
    def get_top_rated_anime(self, limit: int = 30) -> List[Dict]:
        """Get top-rated anime using AniList API"""
        try:
            import requests as direct_requests
            
            # Check cache first
            cache_key = f"top_rated_{limit}.json"
            cached_results = self.load_cached_data(cache_key, max_age_sec=7200)  # 2 hours
            if cached_results:
                return cached_results
            
            # Use AniList API to get top-rated anime by score
            top_rated_gql = '''
            query($limit: Int, $page: Int, $sort: [MediaSort]) {
                Page(page: $page, perPage: $limit) {
                    media(sort: $sort, type: ANIME) {
                        id
                        title { romaji english }
                        episodes
                        coverImage { large }
                        description
                        status
                        genres
                        averageScore
                        popularity
                        startDate { year month day }
                        studios { nodes { name } }
                        tags { name }
                    }
                }
            }
            '''
            
            variables = {
                "limit": limit,
                "page": 1,
                "sort": ["SCORE_DESC", "POPULARITY_DESC"]  # Sort by highest score first
            }
            
            # Rate limiting for AniList API
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                time.sleep(sleep_time)
            
            # Use direct requests instead of session to avoid conflicts
            response = direct_requests.post(
                'https://graphql.anilist.co',
                json={
                    'query': top_rated_gql,
                    'variables': variables
                },
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for media in data.get('data', {}).get('Page', {}).get('media', []):
                    # Only include anime with decent scores
                    score = media.get('averageScore', 0)
                    if score and score >= 70:  # Only high-rated anime
                        anime_title = media.get('title', {}).get('romaji', '') or media.get('title', {}).get('english', '')
                        
                        # Add small delay between AllAnime searches
                        time.sleep(0.2)
                        allanime_id = self._find_allanime_id(anime_title)
                        
                        anime_info = {
                            'id': allanime_id or str(media.get('id')),
                            'anilist_id': str(media.get('id')),
                            'title': anime_title,
                            'episodes': media.get('episodes', 0),
                            'thumbnail': media.get('coverImage', {}).get('large', ''),
                            'description': media.get('description', ''),
                            'status': media.get('status'),
                            'genres': media.get('genres', []),
                            'score': score,
                            'popularity': media.get('popularity'),
                            'studios': [studio.get('name') for studio in media.get('studios', {}).get('nodes', [])],
                            'tags': [tag.get('name') for tag in media.get('tags', [])],
                            'start_date': media.get('startDate', {}),
                            'type': 'TV',
                            'year': media.get('startDate', {}).get('year'),
                            'rating_rank': len(results) + 1
                        }
                        results.append(anime_info)
                
                # Cache and return results
                self.cache_data(cache_key, results)
                return results
            
        except Exception as e:
            self.logger.error(f"Top rated anime error: {e}")
            return []
    
    def _get_current_season(self) -> str:
        """Get current anime season"""
        from datetime import datetime
        month = datetime.now().month
        if month in [12, 1, 2]:
            return "WINTER"
        elif month in [3, 4, 5]:
            return "SPRING"
        elif month in [6, 7, 8]:
            return "SUMMER"
        else:
            return "FALL"

    
    def get_episode_sources(self, anime_id: str, episode: str, anime_title: str = None) -> List[Dict]:
        """Get episode sources using original scraper that works"""
        try:
            if not anime_id or not anime_id.strip() or not episode or not episode.strip():
                return []
            
            # Use original scraper that works with AllAnime API
            sources = self.original_scraper.get_episode_sources(anime_id.strip(), episode.strip())
            
            if not sources:
                print(f"No sources found for anime {anime_id}, episode {episode}")
                return []
            
            # Convert to mobile-friendly format and limit to 3 sources
            mobile_sources = []
            for source in sources[:3]:  # Limit to 3 sources for mobile
                # Keep the original format but ensure all required fields
                mobile_source = {
                    'source': source.get('source', 'Unknown'),
                    'quality': source.get('quality', 'Unknown'),
                    'url': source.get('url', ''),
                    'type': source.get('type', 'embed')
                }
                
                if mobile_source['url']:  # Only add if URL is present
                    mobile_sources.append(mobile_source)
            
            return mobile_sources
            
        except Exception as e:
            self.logger.error(f"Episode sources error: {e}")
            return []
    
    
    def clear_cache(self):
        """Clear all cached data"""
        try:
            for cache_file in self.cache_dir.glob('*.json'):
                cache_file.unlink()
            print("Cache cleared successfully")
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False
    
    def get_cache_size(self):
        """Get total cache size in MB"""
        try:
            total_size = sum(f.stat().st_size for f in self.cache_dir.rglob('*') if f.is_file())
            return round(total_size / (1024 * 1024), 2)
        except Exception as e:
            print(f"Error getting cache size: {e}")
            return 0
    
    def _find_allanime_id(self, anime_title: str) -> str:
        """Try to find AllAnime ID for a given title (simplified for mobile with rate limiting)"""
        try:
            # Skip search for very short titles or empty titles
            if not anime_title or len(anime_title.strip()) < 3:
                return None
                
            # For mobile, we'll do a simple search and try to match (limit to 2 results to reduce load)
            search_results = self.search_anime(anime_title, limit=2)
            if search_results:
                # Return the first result's ID if titles match closely
                for result in search_results:
                    result_title = result.get('title', '').lower()
                    search_title = anime_title.lower()
                    if (search_title in result_title or 
                        result_title in search_title or
                        self._title_similarity(search_title, result_title) > 0.8):
                        return result.get('id')
            return None
        except Exception as e:
            self.logger.debug(f"Error finding AllAnime ID for '{anime_title}': {e}")
            return None
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate similarity between two titles (simple version)"""
        try:
            title1 = title1.lower().strip()
            title2 = title2.lower().strip()
            
            if title1 == title2:
                return 1.0
            
            # Simple word-based similarity
            words1 = set(title1.split())
            words2 = set(title2.split())
            
            if not words1 or not words2:
                return 0.0
            
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            return intersection / union if union > 0 else 0.0
        except:
            return 0.0
    
    def get_recent_releases(self, limit: int = 20) -> List[Dict]:
        """Get recent anime releases using AniList API"""
        try:
            import requests as direct_requests
            
            # Check cache first
            cache_key = f"recent_releases_{limit}.json"
            cached_results = self.load_cached_data(cache_key, max_age_sec=1800)  # 30 minutes
            if cached_results:
                return cached_results
            
            # Use AniList API to get recently released anime
            recent_gql = '''
            query($limit: Int, $page: Int, $sort: [MediaSort]) {
                Page(page: $page, perPage: $limit) {
                    media(sort: $sort, type: ANIME, status: RELEASING) {
                        id
                        title { romaji english }
                        episodes
                        coverImage { large }
                        description
                        status
                        genres
                        averageScore
                        popularity
                        startDate { year month day }
                        studios { nodes { name } }
                        nextAiringEpisode { episode timeUntilAiring }
                    }
                }
            }
            '''
            
            variables = {
                "limit": limit,
                "page": 1,
                "sort": ["START_DATE_DESC", "POPULARITY_DESC"]  # Sort by most recently started
            }
            
            # Rate limiting for AniList API
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                time.sleep(sleep_time)
            
            # Use direct requests instead of session to avoid conflicts
            response = direct_requests.post(
                'https://graphql.anilist.co',
                json={
                    'query': recent_gql,
                    'variables': variables
                },
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            self.last_request_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                results = []
                
                for media in data.get('data', {}).get('Page', {}).get('media', []):
                    anime_title = media.get('title', {}).get('romaji', '') or media.get('title', {}).get('english', '')
                    
                    # Add small delay between AllAnime searches
                    time.sleep(0.2)
                    allanime_id = self._find_allanime_id(anime_title)
                    
                    # Get next episode info
                    next_episode = media.get('nextAiringEpisode', {})
                    next_ep_num = next_episode.get('episode', 0) if next_episode else 0
                    time_until = next_episode.get('timeUntilAiring', 0) if next_episode else 0
                    
                    anime_info = {
                        'id': allanime_id or str(media.get('id')),
                        'anilist_id': str(media.get('id')),
                        'title': anime_title,
                        'episodes': media.get('episodes', 0) or 0,
                        'thumbnail': media.get('coverImage', {}).get('large', ''),
                        'description': media.get('description', ''),
                        'status': media.get('status'),
                        'genres': media.get('genres', []),
                        'score': media.get('averageScore', 0),
                        'popularity': media.get('popularity'),
                        'studios': [studio.get('name') for studio in media.get('studios', {}).get('nodes', [])],
                        'start_date': media.get('startDate', {}),
                        'next_episode': next_ep_num,
                        'time_until_next': time_until,
                        'type': 'TV',
                        'year': media.get('startDate', {}).get('year')
                    }
                    results.append(anime_info)
                
                # Cache and return results
                self.cache_data(cache_key, results)
                return results
            
        except Exception as e:
            self.logger.error(f"Recent releases error: {e}")
            return []
        
        return []
    
    def _get_current_season(self) -> str:
        """Get current anime season based on date"""
        from datetime import datetime
        
        month = datetime.now().month
        
        if month in [12, 1, 2]:
            return 'WINTER'
        elif month in [3, 4, 5]:
            return 'SPRING'
        elif month in [6, 7, 8]:
            return 'SUMMER'
        else:  # month in [9, 10, 11]
            return 'FALL'
