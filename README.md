# Anime Backend API

Django REST Framework backend za Anime aplikaciju sa scraping funkcionalnostima.

## Pokretanje

```bash
# Instaliraj zavisnosti
pip install -r requirements.txt

# Migracija
python manage.py migrate

# Pokretanje
python manage.py runserver
```

## API Endpoints

Base URL: `http://localhost:8000/api/`

### 1. Health Check
**GET** `/api/health/`

Provera da li API radi.

**Response:**
```json
{
  "status": "healthy",
  "scraper_available": true,
  "timestamp": "2025-07-29 14:59:00"
}
```

### 2. Search Anime
**GET** `/api/search/?query={search_term}&limit={number}`

Pretraga anime po nazivu.

**Parameters:**
- `query` (required): Tekst za pretragu
- `limit` (optional): Broj rezultata (default: 20)

**Example:** `/api/search/?query=naruto&limit=10`

**Response:**
```json
{
  "success": true,
  "query": "naruto",
  "count": 10,
  "results": [
    {
      "id": "123",
      "title": "Naruto",
      "episodes": 220,
      "thumbnail": "https://...",
      "description": "...",
      "status": "FINISHED",
      "genres": ["Action", "Adventure"],
      "score": 85
    }
  ]
}
```

### 3. Get Episodes
**GET** `/api/anime/{anime_id}/episodes/`

Dobijanje liste epizoda za anime.

**Parameters:**
- `anime_id`: ID anime-a

**Example:** `/api/anime/123/episodes/`

**Response:**
```json
{
  "success": true,
  "anime_id": "123",
  "episodes_count": 220,
  "episodes": ["1", "2", "3", "..."]
}
```

### 4. Get Episode Sources
**GET** `/api/anime/{anime_id}/episode/{episode}/sources/`

Dobijanje streaming izvora za konkretnu epizodu.

**Parameters:**
- `anime_id`: ID anime-a
- `episode`: Broj epizode

**Example:** `/api/anime/123/episode/1/sources/`

**Response:**
```json
{
  "success": true,
  "anime_id": "123",
  "episode": "1",
  "sources_count": 3,
  "sources": [
    {
      "source": "vidstream",
      "quality": "1080p",
      "url": "https://...",
      "type": "mp4"
    }
  ]
}
```

### 5. Trending Anime
**GET** `/api/trending/?limit={number}&period={time_period}`

Najpopularniji anime trenutno.

**Parameters:**
- `limit` (optional): Broj rezultata (default: 20)
- `period` (optional): Vremenski period - day, week, month, all_time (default: week)

**Example:** `/api/trending/?limit=15&period=week`

**Response:**
```json
{
  "success": true,
  "period": "week",
  "count": 15,
  "results": [...]
}
```

### 6. Top Rated Anime
**GET** `/api/top-rated/?limit={number}`

Najbolje ocenjeni anime (koristi AniList API).

**Parameters:**
- `limit` (optional): Broj rezultata (default: 20)

**Example:** `/api/top-rated/?limit=25`

**Response:**
```json
{
  "success": true,
  "count": 25,
  "results": [
    {
      "id": "456",
      "title": "Attack on Titan",
      "episodes": 25,
      "thumbnail": "https://...",
      "description": "...",
      "status": "FINISHED",
      "genres": ["Action", "Drama"],
      "score": 95,
      "popularity": 500000,
      "studios": ["Studio Wit"]
    }
  ]
}
```

### 7. Seasonal Anime
**GET** `/api/seasonal/?limit={number}&season={season}&year={year}`

Sezonski anime.

**Parameters:**
- `limit` (optional): Broj rezultata (default: 20)
- `season` (optional): WINTER, SPRING, SUMMER, FALL (default: FALL)
- `year` (optional): Godina (default: trenutna godina)

**Example:** `/api/seasonal/?season=WINTER&year=2025&limit=20`

**Response:**
```json
{
  "success": true,
  "season": "WINTER",
  "year": 2025,
  "count": 20,
  "results": [
    {
      "id": "789",
      "title": "New Anime 2025",
      "episodes": 12,
      "thumbnail": "https://...",
      "description": "...",
      "status": "RELEASING",
      "genres": ["Romance", "Comedy"],
      "score": 78,
      "season": "WINTER",
      "seasonYear": 2025,
      "studios": ["Studio A"]
    }
  ]
}
```

### 8. Recent Releases
**GET** `/api/recent/?limit={number}`

Najnovije objavljeni anime.

**Parameters:**
- `limit` (optional): Broj rezultata (default: 20)

**Example:** `/api/recent/?limit=30`

**Response:**
```json
{
  "success": true,
  "count": 30,
  "results": [...]
}
```

### 9. 🚀 Resolve Source (KLJUČNI ENDPOINT)
**POST** `/api/resolve_source/`

**OVAJ ENDPOINT REŠAVA TVOJ GLAVNI PROBLEM!** Prima embed linkove (kao OK.ru) i vraća direktne, playable video linkove.

**Body:**
```json
{
  "source_url": "https://ok.ru/video/embed/123456"
}
```

**Example Request:**
```bash
curl -X POST http://localhost:8000/api/resolve_source/ \
  -H "Content-Type: application/json" \
  -d '{"source_url": "https://ok.ru/video/embed/123456"}'
```

**Response (Success):**
```json
{
  "success": true,
  "playable_url": "https://direct-video-url.com/video.mp4",
  "source_type": "ok.ru",
  "headers": {
    "Referer": "https://allmanga.to",
    "User-Agent": "Mozilla/5.0..."
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Failed to resolve OK.ru URL: Connection timeout"
}
```

**Podržani izvori:**
- ✅ **OK.ru** - Parsira HTML i izvlači direktne video linkove
- ✅ **tools.fast4speed.rsvp** - Rukuje fast4speed linkovima  
- ✅ **Generic** - Opšti parser za druge embed sajtove
- ✅ **Direct links** - Ako je već direktan link (.mp4, .m3u8), vraća ga nazad

## Errors

Svi endpoint-i vraćaju error format:

```json
{
  "error": "Description of what went wrong"
}
```

Status kodovi:
- `400`: Bad Request (nedostaju parametri)
- `500`: Internal Server Error (scraper problem)
- `503`: Service Unavailable (scraper nije dostupan)

## Flutter Integration

Za Flutter aplikaciju, možeš koristiti `http` paket:

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class AnimeService {
  final String baseUrl = 'http://localhost:8000/api';
  
  Future<List<dynamic>> searchAnime(String query) async {
    final response = await http.get(
      Uri.parse('$baseUrl/search/?query=$query')
    );
    
    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      return data['results'];
    }
    throw Exception('Failed to search anime');
  }
  
  Future<List<dynamic>> getTrending() async {
    final response = await http.get(
      Uri.parse('$baseUrl/trending/')
    );
    
    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      return data['results'];
    }
    throw Exception('Failed to get trending');
  }
  
  // Add more methods...
}
```

## Deployment na Railway

1. Napravi `railway.json`:
```json
{
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt && python manage.py migrate"
  },
  "deploy": {
    "startCommand": "python manage.py runserver 0.0.0.0:$PORT"
  }
}
```

2. Dodaj u `settings.py`:
```python
import os
ALLOWED_HOSTS = ['*']  # Za production koristi specifične hostove
```

3. Deploy na Railway:
```bash
railway login
railway link
railway up
```

API će biti dostupan na Railway URL-u koji dobiješ.
