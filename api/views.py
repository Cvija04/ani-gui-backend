from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from django.http import JsonResponse
import requests
import json
from typing import List, Dict

# Import your scraper
try:
    from .config_mobile import ConfigManagerMobile
    from .enhanced_scraper_mobile import EnhancedAnimeScraperMobile
    from .scraper import AnimeScraper
except ImportError:
    # Fallback if import fails
    ConfigManagerMobile = None
    EnhancedAnimeScraperMobile = None
    AnimeScraper = None

# Initialize scraper instance
class AnimeAPI:
    def __init__(self, config_manager):
        try:
            # Use the passed config manager
            self.config_manager = config_manager
            # Use enhanced scraper as primary
            self.scraper = EnhancedAnimeScraperMobile(self.config_manager) if EnhancedAnimeScraperMobile else None
            # Fallback to original scraper
            self.original_scraper = AnimeScraper(self.config_manager) if AnimeScraper else None
        except Exception as e:
            print(f"Scraper initialization error: {e}")
            self.scraper = None
            self.original_scraper = None
            self.config_manager = None
    
    def get_scraper(self):
        return self.scraper or self.original_scraper

# Initialize Config Manager and API instance
config_manager = ConfigManagerMobile() if ConfigManagerMobile else None
api_instance = AnimeAPI(config_manager=config_manager)

class SearchAnimeView(APIView):
    """Search for anime by query"""
    
    def get(self, request):
        try:
            query = request.query_params.get('query', '').strip()
            limit = int(request.query_params.get('limit', 20))
            
            if not query:
                return Response({
                    'error': 'Query parameter is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            scraper = api_instance.get_scraper()
            if not scraper:
                return Response({
                    'error': 'Scraper not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            results = scraper.search_anime(query, limit)
            
            return Response({
                'success': True,
                'query': query,
                'count': len(results),
                'results': results
            })
            
        except Exception as e:
            return Response({
                'error': f'Search failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetEpisodesView(APIView):
    """Get episodes list for specific anime"""
    
    def get(self, request, anime_id):
        try:
            scraper = api_instance.get_scraper()
            if not scraper:
                return Response({
                    'error': 'Scraper not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            episodes = scraper.get_episodes_list(anime_id)
            
            return Response({
                'success': True,
                'anime_id': anime_id,
                'episodes_count': len(episodes),
                'episodes': episodes
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to get episodes: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetEpisodeSourcesView(APIView):
    """Get streaming sources for specific episode"""
    
    def get(self, request, anime_id, episode):
        try:
            scraper = api_instance.get_scraper()
            if not scraper:
                return Response({
                    'error': 'Scraper not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            sources = scraper.get_episode_sources(anime_id, episode)
            
            return Response({
                'success': True,
                'anime_id': anime_id,
                'episode': episode,
                'sources_count': len(sources),
                'sources': sources
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to get sources: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TrendingAnimeView(APIView):
    """Get trending anime"""
    
    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 20))
            time_period = request.query_params.get('period', 'week')  # day, week, month, all_time
            
            scraper = api_instance.get_scraper()
            if not scraper:
                return Response({
                    'error': 'Scraper not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Use enhanced scraper method if available
            if hasattr(scraper, 'get_trending_anime'):
                results = scraper.get_trending_anime(limit, time_period)
            else:
                results = []
            
            return Response({
                'success': True,
                'period': time_period,
                'count': len(results),
                'results': results
            })
            
        except Exception as e:
            return Response({
                'error': f'Failed to get trending anime: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TopRatedAnimeView(APIView):
    """Get top rated anime using enhanced scraper"""
    
    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 30))
            
            scraper = api_instance.get_scraper()
            if not scraper:
                return Response({
                    'error': 'Scraper not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Use enhanced scraper method if available
            if hasattr(scraper, 'get_top_rated_anime'):
                results = scraper.get_top_rated_anime(limit)
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
            
            scraper = api_instance.get_scraper()
            if not scraper:
                return Response({
                    'error': 'Scraper not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Use enhanced scraper method if available
            if hasattr(scraper, 'get_seasonal_anime'):
                import datetime
                current_year = datetime.datetime.now().year
                year = int(year) if year else current_year
                results = scraper.get_seasonal_anime(year, season)
                
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
            
            scraper = api_instance.get_scraper()
            if not scraper:
                return Response({
                    'error': 'Scraper not available'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Use enhanced scraper method if available
            if hasattr(scraper, 'get_recent_releases'):
                results = scraper.get_recent_releases(limit)
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
            'scraper_available': api_instance.get_scraper() is not None,
            'timestamp': json.dumps(str(__import__('datetime').datetime.now()), default=str)
        })
