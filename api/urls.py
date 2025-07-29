from django.urls import path
from .views import (
    SearchAnimeView,
    GetEpisodesView,
    GetEpisodeSourcesView,
    TrendingAnimeView,
    TopRatedAnimeView,
    SeasonalAnimeView,
    RecentReleasesView,
    HealthCheckView
)

urlpatterns = [
    # Health check
    path('health/', HealthCheckView.as_view(), name='health_check'),
    
    # Search
    path('search/', SearchAnimeView.as_view(), name='search_anime'),
    
    # Anime details
    path('anime/<str:anime_id>/episodes/', GetEpisodesView.as_view(), name='get_episodes'),
    path('anime/<str:anime_id>/episode/<str:episode>/sources/', GetEpisodeSourcesView.as_view(), name='get_episode_sources'),
    
    # Categories
    path('trending/', TrendingAnimeView.as_view(), name='trending_anime'),
    path('top-rated/', TopRatedAnimeView.as_view(), name='top_rated_anime'),
    path('seasonal/', SeasonalAnimeView.as_view(), name='seasonal_anime'),
    path('recent/', RecentReleasesView.as_view(), name='recent_releases'),
]
