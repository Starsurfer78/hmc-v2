import aiohttp
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any


class PlexClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    def _with_token(self, path: str) -> str:
        if not path:
            return ""
        if path.startswith("http://") or path.startswith("https://"):
            sep = "&" if "?" in path else "?"
            return f"{path}{sep}X-Plex-Token={self.token}"
        sep = "&" if "?" in path else "?"
        return f"{self.base_url}{path}{sep}X-Plex-Token={self.token}"

    async def _get_text(self, path: str, params: Optional[dict] = None) -> str:
        if not self.session:
            await self.start()
        url = f"{self.base_url}{path}"
        q = dict(params or {})
        q["X-Plex-Token"] = self.token
        async with self.session.get(url, params=q, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def _get_xml(self, path: str, params: Optional[dict] = None) -> ET.Element:
        text = await self._get_text(path, params=params)
        return ET.fromstring(text)

    async def get_sections(self) -> List[Dict]:
        root = await self._get_xml("/library/sections")
        sections: List[Dict] = []
        for directory in root.findall(".//Directory"):
            key = directory.get("key") or ""
            title = directory.get("title") or ""
            section_type = directory.get("type") or ""
            sections.append({"id": key, "name": title, "type": section_type})
        return sections

    async def get_artists(self, section_id: str) -> List[Dict[str, Any]]:
        return await self._paged_list(
            f"/library/sections/{section_id}/all",
            item_tag="Directory",
            params={"type": "8", "sort": "titleSort"},
            mapper=self._map_artist,
        )

    async def get_albums(self, artist_id: str) -> List[Dict[str, Any]]:
        return await self._paged_list(
            f"/library/metadata/{artist_id}/children",
            item_tag="Directory",
            params={"type": "9", "sort": "year:desc,titleSort"},
            mapper=self._map_album,
        )

    async def get_tracks(self, album_id: str) -> List[Dict[str, Any]]:
        return await self._paged_list(
            f"/library/metadata/{album_id}/children",
            item_tag="Track",
            params={"type": "10", "sort": "index"},
            mapper=self._map_track,
        )

    async def _paged_list(
        self,
        path: str,
        item_tag: str,
        params: Dict[str, str],
        mapper,
        page_size: int = 200,
        max_pages: int = 200,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        start = 0
        for _ in range(max_pages):
            p = dict(params)
            p["X-Plex-Container-Start"] = str(start)
            p["X-Plex-Container-Size"] = str(page_size)
            root = await self._get_xml(path, params=p)

            items = root.findall(f".//{item_tag}")
            if not items:
                break

            for it in items:
                mapped = mapper(it)
                if mapped:
                    out.append(mapped)

            start += len(items)

            total_size = root.get("totalSize")
            if total_size is not None:
                try:
                    if start >= int(total_size):
                        break
                except ValueError:
                    pass

            if len(items) < page_size:
                break
        return out

    def _map_artist(self, node: ET.Element) -> Dict[str, Any]:
        rid = node.get("ratingKey") or node.get("key") or ""
        name = node.get("title") or ""
        thumb = node.get("thumb") or ""
        return {"id": rid, "name": name, "image": self._with_token(thumb) if thumb else None}

    def _map_album(self, node: ET.Element) -> Dict[str, Any]:
        rid = node.get("ratingKey") or node.get("key") or ""
        name = node.get("title") or ""
        year = node.get("year")
        thumb = node.get("thumb") or ""
        return {
            "id": rid,
            "name": name,
            "year": int(year) if year and year.isdigit() else None,
            "image": self._with_token(thumb) if thumb else None,
        }

    def _map_track(self, node: ET.Element) -> Dict[str, Any]:
        rid = node.get("ratingKey") or ""
        name = node.get("title") or ""
        duration_ms = node.get("duration") or "0"
        thumb = node.get("thumb") or ""
        duration = 0.0
        try:
            duration = int(duration_ms) / 1000.0
        except ValueError:
            duration = 0.0

        part_key = ""
        media = node.find(".//Media")
        if media is not None:
            part = media.find(".//Part")
            if part is not None:
                part_key = part.get("key") or ""

        return {
            "id": rid,
            "name": name,
            "url": self._with_token(part_key) if part_key else "",
            "duration": duration,
            "image": self._with_token(thumb) if thumb else None,
        }
