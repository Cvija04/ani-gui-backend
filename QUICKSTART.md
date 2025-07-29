# Quick Start Guide - Anime Backend

## 🚀 Brzo Pokretanje

1. **Instaliraj zavisnosti:**
   ```bash
   cd anime_backend
   pip install -r requirements.txt
   ```

2. **Migracija baze:**
   ```bash
   python manage.py migrate
   ```

3. **Pokreni server:**
   ```bash
   python manage.py runserver
   ```

4. **Testiraj API:**
   ```bash
   # Health check
   curl http://127.0.0.1:8000/api/health/
   
   # Top rated anime (koristi AniList - uvek radi)
   curl "http://127.0.0.1:8000/api/top-rated/?limit=5"
   
   # Seasonal anime
   curl "http://127.0.0.1:8000/api/seasonal/?season=WINTER&limit=5"
   
   # Search (koristi tvoj scraper)
   curl "http://127.0.0.1:8000/api/search/?query=naruto&limit=5"
   ```

## 📱 Flutter Integration

```dart
class AnimeService {
  final String baseUrl = 'http://localhost:8000/api';
  
  Future<Map<String, dynamic>> searchAnime(String query) async {
    final response = await http.get(
      Uri.parse('$baseUrl/search/?query=${Uri.encodeComponent(query)}')
    );
    
    if (response.statusCode == 200) {
      return json.decode(response.body);
    }
    throw Exception('Failed to search anime');
  }
  
  Future<Map<String, dynamic>> getTrending() async {
    final response = await http.get(Uri.parse('$baseUrl/trending/'));
    return json.decode(response.body);
  }
  
  Future<Map<String, dynamic>> getTopRated() async {
    final response = await http.get(Uri.parse('$baseUrl/top-rated/'));
    return json.decode(response.body);
  }
  
  Future<Map<String, dynamic>> getSeasonal(String season) async {
    final response = await http.get(
      Uri.parse('$baseUrl/seasonal/?season=$season')
    );
    return json.decode(response.body);
  }
}
```

## 🚂 Railway Deployment

1. **Push na GitHub**
2. **Konektuj Railway:** railway.app → Connect GitHub repo
3. **Automatski deploy:** Railway će prepoznati Django i deploy-ovati

## 📋 Dostupni Endpoints

| Endpoint | Opis | Primer |
|----------|------|--------|
| `/api/health/` | Health check | Uvek radi |
| `/api/search/` | Pretraga anime | Zavisi od scraper-a |
| `/api/trending/` | Trending anime | Zavisi od scraper-a |
| `/api/top-rated/` | Top rated | ✅ Koristi AniList |
| `/api/seasonal/` | Sezonski anime | ✅ Koristi AniList |
| `/api/anime/{id}/episodes/` | Lista epizoda | Zavisi od scraper-a |
| `/api/anime/{id}/episode/{ep}/sources/` | Video sources | Zavisi od scraper-a |

## ⚠️ Napomene

- **Top Rated** i **Seasonal** endpoint-i koriste AniList API i uvek rade
- **Search**, **Trending**, **Episodes** zavise od tvog scraper-a
- Za produkciju, promeni `ALLOWED_HOSTS` u `settings.py`
- CORS je konfigurisan za development
