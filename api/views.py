from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.http import JsonResponse
import requests
import json
from typing import List, Dict
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse

# Import your scraper
from .simple_config import SimpleConfigManager
from .enhanced_scraper_mobile import EnhancedAnimeScraperMobile
from .logger_mobile import get_logger

# Initialize logger
logger = get_logger("INFO")
# Initialize scraper instance
try:
    config_manager = SimpleConfigManager()
    scraper_instance = EnhancedAnimeScraperMobile(config_manager)
except Exception as e:
    logger = get_logger("INFO")
    logger.error(f"Scraper initialization error: {e}")
    scraper_instance = None


class SearchAnimeView(APIView):
    """Search for anime by query"""
    
    def get(self, request):
        if not scraper_instance:
            return Response({'error': 'Scraper not available'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            query = request.query_params.get('query', '').strip()
            limit = int(request.query_params.get('limit', 20))
            
            if not query:
                return Response({'error': 'Query parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            results = scraper_instance.search_anime(query, limit)
            
            return Response({
                'success': True,
                'query': query,
                'count': len(results),
                'results': results
            })
            
        except Exception as e:
            return Response({'error': f'Search failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetEpisodesView(APIView):
    """Get episodes list for specific anime"""
    
    def get(self, request, anime_id):
        if not scraper_instance:
            return Response({'error': 'Scraper not available'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            episodes = scraper_instance.get_episodes_list(anime_id)
            
            return Response({
                'success': True,
                'anime_id': anime_id,
                'episodes_count': len(episodes),
                'episodes': episodes
            })
            
        except Exception as e:
            return Response({'error': f'Failed to get episodes: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetEpisodeSourcesView(APIView):
    """Get streaming sources for specific episode"""
    
    def get(self, request, anime_id, episode):
        if not scraper_instance:
            return Response({'error': 'Scraper not available'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            sources = scraper_instance.get_episode_sources(anime_id, episode)
            
            return Response({
                'success': True,
                'anime_id': anime_id,
                'episode': episode,
                'sources_count': len(sources),
                'sources': sources
            })
            
        except Exception as e:
            return Response({'error': f'Failed to get sources: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResolveSourceView(APIView):
    """Resolve a source URL to a direct, playable video link."""
    def post(self, request):
        try:
            source_url = request.data.get('source_url', '').strip()
            if not source_url:
                return Response({
                    'success': False,
                    'error': 'source_url parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if URL is already a direct video link
            if self._is_direct_video_url(source_url):
                return Response({
                    'success': True,
                    'playable_url': source_url,
                    'source_type': 'direct'
                })
            
            # Handle different source types
            if 'ok.ru' in source_url:
                result = self._resolve_ok_ru(source_url)
            elif 'tools.fast4speed.rsvp' in source_url:
                result = self._resolve_fast4speed(source_url)
            else:
                result = self._resolve_generic(source_url)
            
            return Response(result)
            
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to resolve source: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _is_direct_video_url(self, url: str) -> bool:
        """Check if URL is already a direct video link"""
        video_extensions = ['.mp4', '.m3u8', '.webm', '.mkv', '.avi']
        return any(ext in url.lower() for ext in video_extensions)
    
    def _resolve_ok_ru(self, url: str) -> dict:
        """Resolve OK.ru video URL based on Windows config.py logic"""
        try:
            # Use session with proper headers for OK.ru
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
                'Referer': 'https://allmanga.to',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse the HTML to find video sources
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for video tags or data attributes that contain video URLs
            video_urls = []
            
            # Method 1: Look for video tags
            video_tags = soup.find_all('video')
            for video in video_tags:
                src = video.get('src')
                if src:
                    video_urls.append(src)
                
                # Check source tags within video
                sources = video.find_all('source')
                for source in sources:
                    src = source.get('src')
                    if src:
                        video_urls.append(src)
            
            # Method 2: Look for JSON data in script tags (common for OK.ru)
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string:
                    # Look for video URLs in JavaScript
                    urls = re.findall(r'https?://[^"\s]+\.(?:mp4|m3u8|webm)', script.string)
                    video_urls.extend(urls)
                    
                    # Look for specific OK.ru patterns
                    ok_patterns = re.findall(r'"url":"([^"]+\.(?:mp4|m3u8))"', script.string)
                    video_urls.extend(ok_patterns)
            
            # Method 3: Look for data attributes
            elements_with_data = soup.find_all(attrs={'data-video': True})
            for element in elements_with_data:
                data_video = element.get('data-video')
                if data_video and ('mp4' in data_video or 'm3u8' in data_video):
                    video_urls.append(data_video)
            
            # Clean and validate URLs
            clean_urls = []
            for video_url in video_urls:
                if video_url:
                    # Handle relative URLs
                    if video_url.startswith('//'):
                        video_url = 'https:' + video_url
                    elif video_url.startswith('/'):
                        video_url = urljoin(url, video_url)
                    
                    # Unescape if needed
                    video_url = video_url.replace('\\/', '/')
                    
                    if self._is_valid_video_url(video_url):
                        clean_urls.append(video_url)
            
            if clean_urls:
                # Return the best quality URL (prefer mp4 over m3u8)
                best_url = self._select_best_video_url(clean_urls)
                return {
                    'success': True,
                    'playable_url': best_url,
                    'source_type': 'ok.ru',
                    'headers': {
                        'Referer': 'https://allmanga.to',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'No video URLs found in OK.ru page'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to resolve OK.ru URL: {str(e)}'
            }
    
    def _resolve_fast4speed(self, url: str) -> dict:
        """Resolve tools.fast4speed.rsvp URL"""
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
                'Referer': 'https://allmanga.to'
            })
            
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            # For fast4speed, often the URL itself might be the direct link
            # or we need to parse the response for embedded video
            if self._is_direct_video_url(response.url):
                return {
                    'success': True,
                    'playable_url': response.url,
                    'source_type': 'fast4speed',
                    'headers': {
                        'Referer': 'https://allmanga.to'
                    }
                }
            
            # Parse HTML for video sources
            soup = BeautifulSoup(response.content, 'html.parser')
            video_urls = self._extract_video_urls_from_html(soup, url)
            
            if video_urls:
                best_url = self._select_best_video_url(video_urls)
                return {
                    'success': True,
                    'playable_url': best_url,
                    'source_type': 'fast4speed',
                    'headers': {
                        'Referer': 'https://allmanga.to'
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'No video URLs found in fast4speed page'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to resolve fast4speed URL: {str(e)}'
            }
    
    def _resolve_generic(self, url: str) -> dict:
        """Generic resolver for other embed sources"""
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://allmanga.to'
            })
            
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            video_urls = self._extract_video_urls_from_html(soup, url)
            
            if video_urls:
                best_url = self._select_best_video_url(video_urls)
                return {
                    'success': True,
                    'playable_url': best_url,
                    'source_type': 'generic'
                }
            else:
                return {
                    'success': False,
                    'error': 'No video URLs found in the page'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to resolve generic URL: {str(e)}'
            }
    
    def _extract_video_urls_from_html(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract video URLs from HTML soup"""
        video_urls = []
        
        # Method 1: Video and source tags
        for tag in soup.find_all(['video', 'source']):
            src = tag.get('src')
            if src:
                video_urls.append(src)
        
        # Method 2: Script tags with video URLs
        for script in soup.find_all('script'):
            if script.string:
                # Common patterns for video URLs
                patterns = [
                    r'https?://[^"\s]+\.(?:mp4|m3u8|webm|mkv)',
                    r'"file":"([^"]+)"',
                    r'"url":"([^"]+)"',
                    r'src:"([^"]+)"'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, script.string)
                    video_urls.extend(matches)
        
        # Method 3: iframes (for nested embeds)
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src')
            if src and any(domain in src for domain in ['streamtape', 'mixdrop', 'doodstream']):
                # These would need recursive resolution
                video_urls.append(src)
        
        # Clean and make absolute URLs
        clean_urls = []
        for url in video_urls:
            if url:
                # Handle escaped URLs
                url = url.replace('\\/', '/')
                
                # Make absolute URLs
                if url.startswith('//'):
                    url = 'https:' + url
                elif url.startswith('/'):
                    url = urljoin(base_url, url)
                
                if self._is_valid_video_url(url):
                    clean_urls.append(url)
        
        return clean_urls
    
    def _is_valid_video_url(self, url: str) -> bool:
        """Check if URL looks like a valid video URL"""
        if not url or len(url) < 10:
            return False
        
        # Must be HTTP(S)
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Should contain video-related patterns
        video_indicators = ['.mp4', '.m3u8', '.webm', '.mkv', '.avi', 'video', 'stream']
        return any(indicator in url.lower() for indicator in video_indicators)
    
    def _select_best_video_url(self, urls: List[str]) -> str:
        """Select the best video URL from a list"""
        if not urls:
            return None
        
        # Prefer mp4 over m3u8, and higher quality indicators
        def url_score(url):
            score = 0
            url_lower = url.lower()
            
            # Format preferences
            if '.mp4' in url_lower:
                score += 10
            elif '.m3u8' in url_lower:
                score += 5
            
            # Quality indicators
            if '1080' in url_lower:
                score += 8
            elif '720' in url_lower:
                score += 6
            elif '480' in url_lower:
                score += 4
            
            # Prefer shorter URLs (often more direct)
            score -= len(url) / 1000
            
            return score
        
        return max(urls, key=url_score)

class TrendingAnimeView(APIView):
    """Get trending anime"""
    
    def get(self, request):
        if not scraper_instance:
            return Response({'error': 'Scraper not available'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            limit = int(request.query_params.get('limit', 20))
            time_period = request.query_params.get('period', 'week')
            
            results = scraper_instance.get_trending_anime(limit, time_period)
            
            return Response({
                'success': True,
                'period': time_period,
                'count': len(results),
                'results': results
            })
            
        except Exception as e:
            return Response({'error': f'Failed to get trending anime: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TopRatedAnimeView(APIView):
    """Get top rated anime using enhanced scraper"""
    
    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 30))
            
            if not scraper_instance:
                return Response({
                    'error': 'Scraper not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Use enhanced scraper method if available
            if hasattr(scraper_instance, 'get_top_rated_anime'):
                results = scraper_instance.get_top_rated_anime(limit)
            else:
                # Fallback to old GraphQL method
                query = '''
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
                        }
                    }
                }
                '''
                
                variables = {
                    "limit": limit,
                    "page": 1,
                    "sort": ["SCORE_DESC", "POPULARITY_DESC"]
                }
                
                response = requests.post(
                    'https://graphql.anilist.co',
                    json={'query': query, 'variables': variables},
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                results = []
                if response.status_code == 200:
                    data = response.json()
                    media_list = data.get('data', {}).get('Page', {}).get('media', [])
                    
                    for media in media_list:
                        anime_info = {
                            'id': str(media.get('id', '')),
                            'title': media.get('title', {}).get('romaji') or media.get('title', {}).get('english', 'Unknown'),
                            'episodes': media.get('episodes', 0) or 0,
                            'thumbnail': media.get('coverImage', {}).get('large', ''),
                            'description': media.get('description', ''),
                            'status': media.get('status', ''),
                            'genres': media.get('genres', []),
                            'score': media.get('averageScore', 0) or 0,
                            'popularity': media.get('popularity', 0) or 0,
                            'studios': [studio.get('name', '') for studio in media.get('studios', {}).get('nodes', [])]
                        }
                        results.append(anime_info)
                else:
                    return Response({
                        'error': 'Failed to fetch top rated anime from AniList'
                    }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            return Response({
                'success': True,
                'count': len(results),
                'results': results
            })
                
        except Exception as e:
            return Response({
                'error': f'Failed to get top rated anime: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SeasonalAnimeView(APIView):
    """Get seasonal anime using enhanced scraper"""
    
    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 30))
            year = request.query_params.get('year')  # Optional
            season = request.query_params.get('season', 'FALL').upper()  # WINTER, SPRING, SUMMER, FALL
            
            if not scraper_instance:
                return Response({
                    'error': 'Scraper not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Use enhanced scraper method if available
            if hasattr(scraper_instance, 'get_seasonal_anime'):
                import datetime
                current_year = datetime.datetime.now().year
                year = int(year) if year else current_year
                results = scraper_instance.get_seasonal_anime(year, season)
                
                return Response({
                    'success': True,
                    'season': season,
                    'year': year,
                    'count': len(results),
                    'results': results
                })
            
            # Fallback to old GraphQL method
            
            # GraphQL query for seasonal anime
            query = '''
            query($limit: Int, $page: Int, $season: MediaSeason, $year: Int, $sort: [MediaSort]) {
                Page(page: $page, perPage: $limit) {
                    media(season: $season, seasonYear: $year, sort: $sort, type: ANIME) {
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
                        season
                        seasonYear
                    }
                }
            }
            '''
            
            # Use current year if not specified
            import datetime
            current_year = datetime.datetime.now().year
            year = int(year) if year else current_year
            
            variables = {
                "limit": limit,
                "page": 1,
                "season": season,
                "year": year,
                "sort": ["POPULARITY_DESC", "SCORE_DESC"]
            }
            
            response = requests.post(
                'https://graphql.anilist.co',
                json={'query': query, 'variables': variables},
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                media_list = data.get('data', {}).get('Page', {}).get('media', [])
                
                results = []
                for media in media_list:
                    anime_info = {
                        'id': str(media.get('id', '')),
                        'title': media.get('title', {}).get('romaji') or media.get('title', {}).get('english', 'Unknown'),
                        'episodes': media.get('episodes', 0) or 0,
                        'thumbnail': media.get('coverImage', {}).get('large', ''),
                        'description': media.get('description', ''),
                        'status': media.get('status', ''),
                        'genres': media.get('genres', []),
                        'score': media.get('averageScore', 0) or 0,
                        'popularity': media.get('popularity', 0) or 0,
                        'season': media.get('season', ''),
                        'seasonYear': media.get('seasonYear', year),
                        'studios': [studio.get('name', '') for studio in media.get('studios', {}).get('nodes', [])]
                    }
                    results.append(anime_info)
                
                return Response({
                    'success': True,
                    'season': season,
                    'year': year,
                    'count': len(results),
                    'results': results
                })
            else:
                return Response({
                    'error': 'Failed to fetch seasonal anime'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                
        except Exception as e:
            return Response({
                'error': f'Failed to get seasonal anime: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RecentReleasesView(APIView):
    """Get recent anime releases"""
    
    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 20))
            
            if not scraper_instance:
                return Response({
                    'error': 'Scraper not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Use enhanced scraper method if available
            if hasattr(scraper_instance, 'get_recent_releases'):
                results = scraper_instance.get_recent_releases(limit)
            else:
                results = []
            
            return Response({
                'success': True,
                'count': len(results),
                'results': results
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to get recent releases: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class HealthCheckView(APIView):
    """Health check endpoint"""
    
    def get(self, request):
        return Response({
            'status': 'healthy',
            'scraper_available': scraper_instance is not None,
            'timestamp': json.dumps(str(__import__('datetime').datetime.now()), default=str)
        })
