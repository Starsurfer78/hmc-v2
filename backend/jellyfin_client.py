import aiohttp
import logging
from typing import List, Dict, Optional
from .config import settings

logger = logging.getLogger(__name__)

class JellyfinClient:
    def __init__(self):
        self.url = settings.JELLYFIN_URL.rstrip('/')
        self.api_key = settings.JELLYFIN_API_KEY
        self.headers = {
            "X-Emby-Token": self.api_key,
            "Accept": "application/json"
        }
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Initialize the client session"""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
            logger.info(f"Connected to Jellyfin at {self.url}")

    async def close(self):
        """Close the client session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """Internal GET helper with error handling"""
        if not self.session:
            await self.start()
        
        url = f"{self.url}{endpoint}"
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"Jellyfin API Error {resp.status}: {url}")
                    return {}
                return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"Jellyfin Connection Error: {e}")
            return {}

    async def get_libraries(self) -> List[dict]:
        """Get all libraries (MediaFolders)"""
        data = await self._get("/Library/MediaFolders")
        return data.get("Items", [])
    
    async def get_artists(self, library_id: str) -> List[dict]:
        """Get artists from a library"""
        params = {
            "ParentId": library_id,
            "Recursive": "true",
            "SortBy": "SortName",
            "Fields": "Overview,ImageTags"
        }
        data = await self._get("/Artists", params=params)
        return data.get("Items", [])
    
    async def get_albums(self, artist_id: str) -> List[dict]:
        """Get albums for an artist"""
        params = {
            "ArtistIds": artist_id,
            "IncludeItemTypes": "MusicAlbum,AudioBook",
            "Recursive": "true",
            "SortBy": "ProductionYear,SortName",
            "Fields": "Overview,ImageTags"
        }
        data = await self._get("/Items", params=params)
        return data.get("Items", [])
    
    async def get_tracks(self, album_id: str) -> List[dict]:
        """Get tracks for an album (or the album itself if it's a single file)"""
        # 1. Check if item is folder (using search endpoint to avoid 400 errors)
        params = {"Ids": album_id, "Fields": "RunTimeTicks,Overview,ImageTags"}
        data = await self._get("/Items", params=params)
        items = data.get("Items", [])
        
        if not items:
            return []
            
        item = items[0]

        # 2. If single file (AudioBook m4b), return as track
        if not item.get("IsFolder", False):
             return [{
                "id": item["Id"],
                "name": item["Name"],
                "url": self.get_stream_url(item["Id"]),
                "duration": item.get("RunTimeTicks", 0) / 10000000,
                "overview": item.get("Overview"),
                "image": self.get_image_url(item["Id"]) if item.get("ImageTags", {}).get("Primary") else None
            }]

        # 3. If folder, fetch children
        params = {
            "ParentId": album_id,
            "SortBy": "ParentIndexNumber,IndexNumber,SortName",
            "Fields": "MediaSources,RunTimeTicks,Overview,ImageTags"
        }
        data = await self._get("/Items", params=params)
        tracks = data.get("Items", [])
        
        return [
            {
                "id": track["Id"],
                "name": track["Name"],
                "url": self.get_stream_url(track["Id"]),
                "duration": track.get("RunTimeTicks", 0) / 10000000,
                "overview": track.get("Overview"),
                "image": self.get_image_url(track["Id"]) if track.get("ImageTags", {}).get("Primary") else None
            }
            for track in tracks
        ]
    
    def get_stream_url(self, item_id: str) -> str:
        """Generate stream URL"""
        return f"{self.url}/Audio/{item_id}/stream.mp3?api_key={self.api_key}"
    
    def get_image_url(self, item_id: str, image_type: str = "Primary") -> Optional[str]:
        """Generate image URL"""
        return f"{self.url}/Items/{item_id}/Images/{image_type}?api_key={self.api_key}"
