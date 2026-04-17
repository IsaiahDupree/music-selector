# MusicLibrary API Documentation

## Overview

MusicLibrary provides a complete REST API for managing, searching, and exporting audio tracks. The API is built with Next.js and integrates with Supabase for data storage and authentication.

## Base URL

```
https://your-domain.com/api
```

For local development:
```
http://localhost:3000/api
```

## Authentication

Currently, the API uses a default user ID for all operations. Future versions will include JWT-based authentication via Supabase Auth.

## Endpoints

### Health Check

#### GET `/api/health`

Health check endpoint for monitoring and deployment verification.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2026-04-17T10:30:00.000Z",
  "services": {
    "api": "ok",
    "database": "ok"
  }
}
```

**Status Codes:**
- `200 OK` - All services healthy
- `500 Internal Server Error` - Service errors

---

### Tracks

#### GET `/api/tracks`

List all tracks with optional filtering and pagination.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `page` | number | Page number (default: 1) |
| `limit` | number | Results per page (default: 20) |
| `genre` | string | Filter by genre |
| `mood` | string | Filter by mood |
| `minDuration` | number | Minimum duration in seconds |
| `maxDuration` | number | Maximum duration in seconds |
| `minEnergy` | number | Minimum energy level (0-1) |
| `maxEnergy` | number | Maximum energy level (0-1) |

**Response:**
```json
{
  "tracks": [
    {
      "id": "uuid",
      "title": "Track Title",
      "artist": "Artist Name",
      "genre": "lofi",
      "mood": "calm",
      "energy_level": 0.4,
      "duration_sec": 180,
      "bpm": 85,
      "is_trending": false,
      "created_at": "2026-04-17T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "totalPages": 8
  }
}
```

**Status Codes:**
- `200 OK` - Success
- `400 Bad Request` - Invalid filters
- `503 Service Unavailable` - Database error

---

#### GET `/api/tracks/{id}`

Get detailed information for a single track.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `id` | uuid | Track ID |

**Response:**
```json
{
  "id": "uuid",
  "title": "Track Title",
  "artist": "Artist Name",
  "genre": "lofi",
  "mood": "calm",
  "energy_level": 0.4,
  "duration_sec": 180,
  "bpm": 85,
  "is_trending": false,
  "metadata": {
    "bitrate": 320,
    "codec": "mp3",
    "sample_rate": 44100,
    "channels": 2,
    "storage_url": "https://..."
  },
  "created_at": "2026-04-17T10:00:00Z"
}
```

**Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Track not found
- `503 Service Unavailable` - Database error

---

#### PUT `/api/tracks/{id}`

Update track information.

**Request Body:**
```json
{
  "title": "New Title",
  "artist": "New Artist",
  "genre": "electronic",
  "mood": "energetic",
  "energy_level": 0.8
}
```

**Response:**
Same as GET track response.

**Status Codes:**
- `200 OK` - Success
- `400 Bad Request` - Invalid data
- `404 Not Found` - Track not found

---

#### DELETE `/api/tracks/{id}`

Delete a track.

**Response:**
```json
{
  "success": true
}
```

**Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Track not found

---

### Upload

#### POST `/api/upload`

Upload a new audio file.

**Request:**
- Content-Type: `multipart/form-data`

**Form Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | File | Yes | Audio file (MP3, WAV, AAC, FLAC, max 100MB) |
| `title` | string | No | Track title (defaults to filename) |
| `artist` | string | No | Artist name |
| `genre` | string | No | Genre classification |

**Response:**
```json
{
  "id": "uuid",
  "title": "Track Title",
  "artist": "Artist Name",
  "genre": "lofi",
  "storage_url": "https://storage.supabase.co/..."
}
```

**Status Codes:**
- `201 Created` - Upload successful
- `400 Bad Request` - Invalid file or parameters
- `503 Service Unavailable` - Storage error

---

### Search

#### GET `/api/search`

Full-text search across track titles and artists.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Search query (min 2 characters) |
| `limit` | number | Max results (default: 10) |

**Response:**
```json
{
  "query": "search term",
  "results": [
    {
      "id": "uuid",
      "title": "Search Result",
      "artist": "Artist",
      "score": 0.95
    }
  ],
  "count": 5
}
```

**Status Codes:**
- `200 OK` - Success
- `400 Bad Request` - Query too short

---

### Filters

#### GET `/api/filters`

Get available filter options.

**Response:**
```json
{
  "genres": ["lofi", "electronic", "house", ...],
  "moods": ["calm", "energetic", "happy", ...],
  "durationRanges": [
    { "label": "0-30s", "min": 0, "max": 30 },
    { "label": "30s-1m", "min": 30, "max": 60 }
  ],
  "energyLevels": [
    { "label": "Low", "min": 0, "max": 0.33 },
    { "label": "Medium", "min": 0.33, "max": 0.67 }
  ]
}
```

---

### Tags

#### GET `/api/tags`

Get all tags.

**Response:**
```json
{
  "tags": [
    { "id": "uuid", "name": "tag-name", "created_at": "..." }
  ]
}
```

---

#### POST `/api/tags`

Create a new tag.

**Request Body:**
```json
{
  "name": "tag-name"
}
```

**Status Codes:**
- `201 Created` - Success
- `400 Bad Request` - Invalid name

---

### Playlists

#### GET `/api/playlists`

Get all playlists.

**Response:**
```json
{
  "playlists": [
    {
      "id": "uuid",
      "name": "Playlist Name",
      "description": "Optional description",
      "created_at": "..."
    }
  ]
}
```

---

#### POST `/api/playlists`

Create a new playlist.

**Request Body:**
```json
{
  "name": "Playlist Name",
  "description": "Optional description"
}
```

**Status Codes:**
- `201 Created` - Success
- `400 Bad Request` - Invalid data

---

### Export

#### GET `/api/export/csv`

Export all tracks as CSV.

**Response:**
- Content-Type: `text/csv`
- CSV file download

**Status Codes:**
- `200 OK` - Success
- `503 Service Unavailable` - Database error

---

#### GET `/api/export/json`

Export all tracks and metadata as JSON.

**Response:**
```json
{
  "version": "1.0",
  "exportDate": "2026-04-17T10:00:00Z",
  "totalTracks": 150,
  "tracks": [...]
}
```

**Status Codes:**
- `200 OK` - Success
- `503 Service Unavailable` - Database error

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Human-readable error message"
}
```

### Common Error Codes

| Code | Message | Reason |
|------|---------|--------|
| 400 | Bad Request | Invalid parameters or request body |
| 404 | Not Found | Resource doesn't exist |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Database or storage unavailable |

---

## Rate Limiting

Currently, there are no rate limits. Future versions may implement rate limiting based on user tier.

---

## Examples

### Upload a track

```bash
curl -X POST http://localhost:3000/api/upload \
  -F "file=@song.mp3" \
  -F "title=My Song" \
  -F "artist=My Artist" \
  -F "genre=lofi"
```

### Search for tracks

```bash
curl "http://localhost:3000/api/search?q=calm&limit=5"
```

### Get filtered tracks

```bash
curl "http://localhost:3000/api/tracks?genre=lofi&mood=calm&minDuration=60"
```

### Export as CSV

```bash
curl "http://localhost:3000/api/export/csv" > library.csv
```
