import requests
import re
import json
from typing import List, Dict, Optional
from urllib.parse import urlencode
import time

class AnimeScraper:
    def __init__(self, config_manager):
        self.config = config_manager
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.config.get('SCRAPING', 'user_agent'),
            'Referer': self.config.get('SCRAPING', 'referer')
        })
        
        self.base_url = self.config.get('SCRAPING', 'base_url')
        self.api_url = self.config.get('SCRAPING', 'api_url')
        self.referer = self.config.get('SCRAPING', 'referer')
    
    def search_anime(self, query: str, limit: int = 40) -> List[Dict]:
        """Search for anime using the API"""
        if not query or not query.strip():
            return []
            
        search_gql = '''
        query($search: SearchInput $limit: Int $page: Int $translationType: VaildTranslationTypeEnumType $countryOrigin: VaildCountryOriginEnumType) {
            shows(search: $search limit: $limit page: $page translationType: $translationType countryOrigin: $countryOrigin) {
                edges {
                    _id
                    name
                    availableEpisodes
                    __typename
                    thumbnail
                    description
                    status
                    genres
                    score
                }
            }
        }
        '''
        
        variables = {
            "search": {
                "allowAdult": False,
                "allowUnknown": False,
                "query": query.strip()
            },
            "limit": limit,
            "page": 1,
            "translationType": "sub",
            "countryOrigin": "ALL"
        }
        
        try:
            response = self.session.get(
                f"{self.api_url}/api",
                params={
                    'variables': json.dumps(variables),
                    'query': search_gql
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if not data or 'data' not in data:
                    return []
                    
                results = []
                edges = data.get('data', {}).get('shows', {}).get('edges', [])
                
                for edge in edges:
                    if not edge or not edge.get('_id'):
                        continue
                        
                    available_episodes = edge.get('availableEpisodes', {})
                    episode_count = 0
                    if available_episodes and isinstance(available_episodes, dict):
                        episode_count = available_episodes.get('sub', 0) or 0
                    
                    anime_info = {
                        'id': str(edge.get('_id', '')).strip(),
                        'title': str(edge.get('name', 'Unknown')).strip(),
                        'episodes': episode_count,
                        'thumbnail': str(edge.get('thumbnail', '')).strip() if edge.get('thumbnail') else '',
                        'description': str(edge.get('description', '')).strip(),
                        'status': str(edge.get('status', '')).strip(),
                        'genres': edge.get('genres', []) if edge.get('genres') else [],
                        'score': edge.get('score', 0) or 0
                    }
                    
                    if anime_info['id'] and anime_info['title']:
                        results.append(anime_info)
                
                return results
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
        
        return []
    
    def get_episodes_list(self, anime_id: str) -> List[str]:
        """Get list of available episodes for an anime"""
        if not anime_id or not anime_id.strip():
            return []
            
        episodes_gql = '''
        query($showId: String!) {
            show(_id: $showId) {
                _id
                availableEpisodesDetail
            }
        }
        '''
        
        variables = {"showId": anime_id.strip()}
        
        try:
            response = self.session.get(
                f"{self.api_url}/api",
                params={
                    'variables': json.dumps(variables),
                    'query': episodes_gql
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if not data or 'data' not in data:
                    return []
                    
                show_data = data.get('data', {}).get('show', {})
                if not show_data:
                    return []
                    
                episodes_detail = show_data.get('availableEpisodesDetail', {})
                if not episodes_detail:
                    return []
                    
                episodes = episodes_detail.get('sub', [])
                if not episodes:
                    return []
                
                valid_episodes = []
                for ep in episodes:
                    if ep is not None and str(ep).strip():
                        try:
                            float(ep)
                            valid_episodes.append(str(ep).strip())
                        except (ValueError, TypeError):
                            valid_episodes.append(str(ep).strip())
                
                return sorted(valid_episodes, key=lambda x: float(x) if x.replace('.', '').isdigit() else 999)
            
        except Exception as e:
            print(f"Episodes list error: {e}")
            return []
        
        return []
    
    def get_episode_sources(self, anime_id: str, episode: str) -> List[Dict]:
        if not anime_id or not anime_id.strip() or not episode or not episode.strip():
            return []

        episode_gql = '''
        query($showId: String!, $translationType: VaildTranslationTypeEnumType!, $episodeString: String!) {
            episode(showId: $showId translationType: $translationType episodeString: $episodeString) {
                episodeString
                sourceUrls
            }
        }
        '''

        variables = {
            "showId": anime_id.strip(),
            "translationType": "sub",
            "episodeString": episode.strip()
        }

        try:
            response = self.session.get(
                f"{self.api_url}/api",
                params={
                    'variables': json.dumps(variables),
                    'query': episode_gql
                }
            )

            if response.status_code == 200:
                data = response.json()
                if not data or 'data' not in data:
                    return []
                episode_data = data.get('data', {}).get('episode', {})
                if not episode_data:
                    return []
                source_urls = episode_data.get('sourceUrls', [])

                for source in source_urls:
                    source_name = source.get("sourceName", "").lower()
                    source_url = source.get("sourceUrl", "").strip()

                    if source_url.startswith("--"):
                        source_url = source_url[2:]

                    if "ok.ru" in source_url:
                        return [{
                            'source': 'ok.ru',
                            'quality': 'embed',
                            'url': source_url,
                            'type': 'embed'
                        }]

                return self._parse_sources(source_urls)

        except Exception as e:
            print(f"Episode sources error: {e}")
            return []

        return []

    def _parse_sources(self, source_urls: List) -> List[Dict]:
        """Parse source URLs and extract video links"""
        if not source_urls:
            return []
            
        sources = []
        
        for source in source_urls:
            if not source or not isinstance(source, dict):
                continue
                
            try:
                source_name = str(source.get('sourceName', 'Unknown')).strip()
                source_url = str(source.get('sourceUrl', '')).strip()
                
                if not source_url:
                    continue
                    
                if source_url.startswith('--'):
                    source_url = source_url[2:].strip()
                
                if not source_url:
                    continue
                
                try:
                    video_links = self._extract_video_links(source_url, source_name)
                except Exception as e:
                    print(f"Error extracting video links from {source_name}: {e}")
                    video_links = []
                
                for link in video_links:
                    if not link or not isinstance(link, dict):
                        continue
                        
                    link_url = str(link.get('url', '')).strip()
                    if not link_url:
                        continue
                        
                    sources.append({
                        'source': source_name,
                        'quality': str(link.get('quality', 'Unknown')).strip(),
                        'url': link_url,
                        'type': str(link.get('type', 'mp4')).strip()
                    })
                    
            except Exception as e:
                print(f"Error parsing source: {e}")
                continue
        
        return sources
    
    def _extract_video_links(self, source_url: str, source_name: str) -> List[Dict]:
        """Extract video links from source URL"""
        if not source_url or not source_url.strip():
            return []
            
        try:
            decoded_url = self._decode_url(source_url)
            if decoded_url and decoded_url != source_url:
                source_url = decoded_url
                
            if self._is_corrupted_url(source_url):
                print(f"Corrupted URL detected, skipping: {source_url[:50]}...")
                return []
                
            if not self._is_valid_url(source_url):
                print(f"Invalid URL format: {source_url[:100]}...")
                return []
                
            if not source_url.startswith(('http://', 'https://')):
                source_url = 'https://' + source_url
                
            response = self.session.get(source_url, headers={'Referer': self.referer}, timeout=5)
            
            if response.status_code == 200:
                content = response.text
                if not content:
                    return []
                    
                links = []
                
                if 'repackager.wixmp.com' in source_url:
                    links = self._parse_wixmp_source(content)
                elif 'master.m3u8' in source_url or '.m3u8' in source_url:
                    links = self._parse_m3u8_source(content, source_url)
                elif 'youtube' in source_name.lower():
                    links = self._parse_youtube_source(content)
                else:
                    links = self._parse_generic_source(content)
                
                valid_links = []
                for link in links:
                    if link and isinstance(link, dict) and link.get('url', '').strip():
                        valid_links.append(link)
                
                return valid_links
                
        except Exception as e:
            print(f"Error extracting video links: {e}")
            return []
        
        return []
    
    def _parse_wixmp_source(self, content: str) -> List[Dict]:
        """Parse Wixmp video sources"""
        links = []
        return links
    
    def _parse_m3u8_source(self, content: str, source_url: str) -> List[Dict]:
        """Parse M3U8 video sources"""
        if not content or not content.strip():
            return []
            
        links = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            if not line or not line.strip():
                continue
                
            line = line.strip()
            if line.startswith('#EXT-X-STREAM-INF'):
                resolution_match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
                if resolution_match:
                    width, height = resolution_match.groups()
                    quality = f"{height}p"
                    
                    if i + 1 < len(lines):
                        stream_url = lines[i + 1].strip()
                        if not stream_url:
                            continue
                            
                        if not stream_url.startswith('http'):
                            try:
                                base_url = '/'.join(source_url.split('/')[:-1])
                                stream_url = f"{base_url}/{stream_url}"
                            except Exception:
                                continue
                        
                        links.append({
                            'quality': quality,
                            'url': stream_url,
                            'type': 'm3u8'
                        })
            elif line.startswith('http') and '.m3u8' in line:
                links.append({
                    'quality': 'Unknown',
                    'url': line,
                    'type': 'm3u8'
                })
        
        return links
    
    def _parse_youtube_source(self, content: str) -> List[Dict]:
        """Parse YouTube video sources"""
        links = []
        return links
    
    def _parse_generic_source(self, content: str) -> List[Dict]:
        """Parse generic video sources"""
        links = []
        return links
    
    def _is_corrupted_url(self, url: str) -> bool:
        """Check if URL contains corrupted characters or patterns"""
        if not url or not url.strip():
            return False
            
        url = url.strip()
        
        if any(ord(c) < 32 for c in url if c != '\n' and c != '\t'):
            return True
            
        if '\n' in url or '\r' in url or '  ' in url:
            return True
            
        corruption_patterns = [
            r'[\x00-\x1f]',
            r'[\\]{2,}',
            r'[\^]{2,}',
            r'\s{2,}',
        ]
        
        for pattern in corruption_patterns:
            if re.search(pattern, url):
                return True
                
        return False
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and properly formatted"""
        if not url or not url.strip():
            return False
            
        url = url.strip()
        
        if url.startswith(('http://', 'https://')):
            return True
            
        if '.' in url and ' ' not in url and len(url) > 3:
            return True
            
        return False
    
    def _decode_url(self, encoded_url: str) -> str:
        """Decode URLs using custom mapping"""
        if not encoded_url or not encoded_url.strip():
            return encoded_url

        original_url = encoded_url.strip()

        if original_url.startswith(('http://', 'https://')):
            return original_url

        try:
            hex_pairs = [original_url[i:i+2] for i in range(0, len(original_url), 2)]

            def hex_to_char(hex_pair):
                mapping = {
                    '79': 'A', '7a': 'B', '7b': 'C', '7c': 'D',
                    '7d': 'E', '7e': 'F', '7f': 'G', '70': 'H',
                    '71': 'I', '72': 'J', '73': 'K', '74': 'L',
                    '75': 'M', '76': 'N', '77': 'O', '68': 'P',
                    '69': 'Q', '6a': 'R', '6b': 'S', '6c': 'T',
                    '6d': 'U', '6e': 'V', '6f': 'W', '60': 'X',
                    '61': 'Y', '62': 'Z', '59': 'a', '5a': 'b',
                    '5b': 'c', '5c': 'd', '5d': 'e', '5e': 'f',
                    '5f': 'g', '50': 'h', '51': 'i', '52': 'j',
                    '53': 'k', '54': 'l', '55': 'm', '56': 'n',
                    '57': 'o', '48': 'p', '49': 'q', '4a': 'r',
                    '4b': 's', '4c': 't', '4d': 'u', '4e': 'v',
                    '4f': 'w', '40': 'x', '41': 'y', '42': 'z',
                    '08': '0', '09': '1', '0a': '2', '0b': '3',
                    '0c': '4', '0d': '5', '0e': '6', '0f': '7',
                    '00': '8', '01': '9', '15': '-', '16': '.',
                    '67': '_', '46': '~', '02': ':', '17': '/',
                    '07': '?', '1b': '#', '63': '[', '65': ']',
                    '78': '@', '19': '!', '1c': '$', '1e': '&',
                    '10': '(', '11': ')', '12': '*', '13': '+',
                    '14': ',', '03': ';', '05': '=', '1d': '%'
                }
                return mapping.get(hex_pair.lower(), '')

            decoded_url = ''.join(hex_to_char(pair) for pair in hex_pairs)
            
            if '/clock' in decoded_url and not decoded_url.endswith('/clock.json'):
                decoded_url = decoded_url.replace('/clock', '/clock.json')
            
            if decoded_url.startswith(('http://', 'https://')):
                return decoded_url

            return original_url

        except Exception as e:
            print(f"Error decoding URL: {e}")
            return original_url
    
    def get_trending_anime(self, limit: int = 20) -> List[Dict]:
        """Get trending anime"""
        return []
    
    def get_recent_releases(self, limit: int = 20) -> List[Dict]:
        """Get recent anime releases"""
        return []