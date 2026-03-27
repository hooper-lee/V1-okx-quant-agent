from __future__ import annotations

from datetime import datetime, timedelta
import re
import xml.etree.ElementTree as ET
from urllib import error, request


class NewsRAGService:
    def __init__(self, runtime_config_service=None) -> None:
        self.runtime_config_service = runtime_config_service
        self._source_items = {
            "Cointelegraph": [
                {
                    "title": "Cointelegraph feed pending refresh",
                    "summary": "默认新闻源已加载，等待刷新抓取真实内容。",
                    "source": "Cointelegraph",
                },
            ],
            "Decrypt": [
                {
                    "title": "Decrypt feed pending refresh",
                    "summary": "默认新闻源已加载，等待刷新抓取真实内容。",
                    "source": "Decrypt",
                },
            ],
            "CryptoSlate": [
                {
                    "title": "CryptoSlate feed pending refresh",
                    "summary": "默认新闻源已加载，等待刷新抓取真实内容。",
                    "source": "CryptoSlate",
                },
            ],
            "Cryptonews": [
                {
                    "title": "Cryptonews feed pending refresh",
                    "summary": "默认新闻源已加载，等待刷新抓取真实内容。",
                    "source": "Cryptonews",
                },
            ],
        }
        self._default_sources = [
            {
                "name": "Cointelegraph",
                "urls": ["https://cointelegraph.com/rss"],
                "enabled": True,
                "priority": 90,
                "ttl_minutes": 15,
                "stable": True,
                "llm_summary": True,
            },
            {
                "name": "Decrypt",
                "urls": ["https://decrypt.co/feed"],
                "enabled": True,
                "priority": 85,
                "ttl_minutes": 15,
                "stable": True,
                "llm_summary": True,
            },
            {
                "name": "CryptoSlate",
                "urls": ["https://cryptoslate.com/feed/"],
                "enabled": True,
                "priority": 80,
                "ttl_minutes": 15,
                "stable": True,
                "llm_summary": True,
            },
            {
                "name": "Cryptonews",
                "urls": ["https://cryptonews.com/news/feed/"],
                "enabled": True,
                "priority": 75,
                "ttl_minutes": 15,
                "stable": True,
                "llm_summary": True,
            },
        ]
        self._cache: dict[tuple[str, str], dict] = {}
        self._source_status = {
            name: {
                "status": "seeded",
                "mode": "fallback",
                "last_refreshed_at": None,
                "last_error": "",
                "item_count": len(items),
                "cache_state": "empty",
                "cache_expires_at": None,
            }
            for name, items in self._source_items.items()
        }

    def _default_source_map(self) -> dict:
        return {item["name"]: item for item in self._default_sources}

    def _normalize_source_item(self, item: dict) -> dict:
        default = self._default_source_map().get(str(item.get("name", "")).strip(), {})
        return {
            "name": str(item.get("name", "")).strip(),
            "urls": [str(url).strip() for url in item.get("urls", []) if str(url).strip()],
            "enabled": bool(item.get("enabled", default.get("enabled", True))),
            "priority": int(item.get("priority", default.get("priority", 50))),
            "ttl_minutes": int(item.get("ttl_minutes", default.get("ttl_minutes", 15))),
            "stable": bool(item.get("stable", default.get("stable", False))),
            "llm_summary": bool(item.get("llm_summary", default.get("llm_summary", False))),
        }

    def _load_feed_config(self) -> list[dict]:
        if self.runtime_config_service is None:
            return self._default_sources
        configured = self.runtime_config_service.get("news_sources")
        if isinstance(configured, list) and configured:
            parsed = []
            for item in configured:
                normalized = self._normalize_source_item(item)
                if normalized["name"]:
                    parsed.append(normalized)
            if parsed:
                return parsed
        return self._default_sources

    def get_source_config(self) -> list[dict]:
        return self._load_feed_config()

    def save_source_config(self, sources: list[dict]) -> list[dict]:
        if self.runtime_config_service is None:
            return self.get_source_config()
        normalized = []
        for item in sources:
            source = self._normalize_source_item(item)
            name = source["name"]
            if name:
                normalized.append(source)
                self._source_items.setdefault(
                    name,
                    [
                        {
                            "title": f"{name} feed pending refresh",
                            "summary": "该新闻源已保存，等待刷新抓取真实内容。",
                            "source": name,
                        }
                    ],
                )
                self._source_status.setdefault(
                    name,
                    {
                        "status": "pending",
                        "mode": "pending",
                        "last_refreshed_at": None,
                        "last_error": "",
                        "item_count": 1,
                        "cache_state": "empty",
                        "cache_expires_at": None,
                    },
                )
        self.runtime_config_service.save({"news_sources": normalized})
        return normalized

    def search(self, symbol: str) -> list[dict]:
        items = []
        for source_name, source_items in self._source_items.items():
            for item in source_items:
                items.append(
                    {
                        "title": f"{symbol} | {item['title']}",
                        "summary": item["summary"],
                        "source": source_name,
                    }
                )
        return items

    def list_sources(self, symbol: str) -> list[dict]:
        configured_items = [item for item in self.get_source_config() if item.get("enabled", True)]
        return [
            {
                "name": source_name,
                "meta": {
                    **self._source_status.get(source_name, {}),
                    "refresh_policy": f"cache:{source_config.get('ttl_minutes', 15)}m",
                    "priority": source_config.get("priority", 50),
                    "stable": source_config.get("stable", False),
                    "llm_summary": source_config.get("llm_summary", False),
                },
                "items": [
                    {
                        "title": item["title"],
                        "summary": item["summary"],
                        "source": item["source"],
                        "published_at": item.get("published_at"),
                        "link": item.get("link"),
                    }
                    for item in source_items
                ],
            }
            for source_config in sorted(configured_items, key=lambda item: item.get("priority", 50), reverse=True)
            for source_name in [source_config["name"]]
            for source_items in [self._source_items.get(source_name, [])]
        ]

    def refresh_sources(self, symbol: str, force: bool = False) -> dict:
        refreshed = []
        for source_config in self._load_feed_config():
            if not source_config.get("enabled", True):
                continue
            source_name = source_config["name"]
            urls = source_config.get("urls", [])
            ttl_minutes = int(source_config.get("ttl_minutes", 15))
            cache_key = (source_name, symbol)
            cache_item = self._cache.get(cache_key)
            if cache_item and not force and cache_item.get("expires_at") and cache_item["expires_at"] > datetime.now():
                cached_items = cache_item.get("items", [])
                self._source_items[source_name] = cached_items
                self._source_status[source_name] = {
                    "status": "success",
                    "mode": "cache",
                    "last_refreshed_at": cache_item.get("refreshed_at"),
                    "last_error": "",
                    "item_count": len(cached_items),
                    "cache_state": "hit",
                    "cache_expires_at": cache_item.get("expires_at").strftime("%Y-%m-%d %H:%M:%S"),
                }
                refreshed.append({"name": source_name, "count": len(cached_items), "mode": "cache", "status": "success"})
                continue
            source_items, failure_reason = self._fetch_feed_items(urls=urls, source_name=source_name, symbol=symbol)
            refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if source_items:
                self._source_items[source_name] = source_items
                expires_at = datetime.now() + timedelta(minutes=ttl_minutes)
                self._cache[cache_key] = {
                    "items": source_items,
                    "expires_at": expires_at,
                    "refreshed_at": refreshed_at,
                }
                self._source_status[source_name] = {
                    "status": "success",
                    "mode": "live",
                    "last_refreshed_at": refreshed_at,
                    "last_error": "",
                    "item_count": len(source_items),
                    "cache_state": "refreshed",
                    "cache_expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
                refreshed.append({"name": source_name, "count": len(source_items), "mode": "live", "status": "success"})
            else:
                existing_count = len(self._source_items.get(source_name, []))
                self._source_status[source_name] = {
                    "status": "fallback" if existing_count else "failed",
                    "mode": "fallback" if existing_count else "failed",
                    "last_refreshed_at": refreshed_at,
                    "last_error": failure_reason,
                    "item_count": existing_count,
                    "cache_state": "stale" if cache_item else "empty",
                    "cache_expires_at": cache_item.get("expires_at").strftime("%Y-%m-%d %H:%M:%S") if cache_item and cache_item.get("expires_at") else None,
                }
                refreshed.append(
                    {
                        "name": source_name,
                        "count": existing_count,
                        "mode": "fallback" if existing_count else "failed",
                        "status": "fallback" if existing_count else "failed",
                        "reason": failure_reason,
                    }
                )
        return {"items": refreshed}

    def _fetch_feed_items(self, urls: list[str], source_name: str, symbol: str) -> tuple[list[dict], str]:
        last_error = ""
        for url in urls:
            try:
                req = request.Request(url, headers={"User-Agent": "Mozilla/5.0 OKX-Quant-Agent/1.0"})
                with request.urlopen(req, timeout=8) as response:
                    payload = response.read()
                items = self._parse_rss(payload=payload, source_name=source_name, symbol=symbol)
                if items:
                    return items[:4], ""
                last_error = "源返回成功，但没有解析出可用新闻条目。"
            except error.HTTPError as exc:
                if exc.code == 429:
                    last_error = "HTTP 429：新闻源限流"
                elif exc.code == 403:
                    last_error = "HTTP 403：新闻源拒绝访问"
                elif exc.code == 404:
                    last_error = "HTTP 404：新闻源地址失效"
                else:
                    last_error = f"HTTP {exc.code}"
            except error.URLError as exc:
                last_error = f"网络错误：{exc.reason}"
            except (TimeoutError, ValueError, ET.ParseError) as exc:
                last_error = f"解析失败：{exc}"
                continue
        return [], last_error or "刷新失败，未获取到有效内容。"

    def _parse_rss(self, payload: bytes, source_name: str, symbol: str) -> list[dict]:
        root = ET.fromstring(payload)
        items = []
        rss_items = root.findall(".//item")
        if rss_items:
            for item in rss_items:
                title = (item.findtext("title") or "").strip()
                summary = (item.findtext("description") or item.findtext("summary") or "").strip()
                published_at = (item.findtext("pubDate") or item.findtext("published") or "").strip()
                link = (item.findtext("link") or "").strip()
                if not title and not summary:
                    continue
                items.append(
                    {
                        "title": title or source_name,
                        "summary": self._clean_text(summary)[:220],
                        "source": source_name,
                        "published_at": published_at,
                        "link": link,
                    }
                )
            return items

        atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for entry in atom_entries:
            title = (entry.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            summary = (
                entry.findtext("{http://www.w3.org/2005/Atom}summary")
                or entry.findtext("{http://www.w3.org/2005/Atom}content")
                or ""
            ).strip()
            published_at = (
                entry.findtext("{http://www.w3.org/2005/Atom}updated")
                or entry.findtext("{http://www.w3.org/2005/Atom}published")
                or ""
            ).strip()
            link = ""
            link_node = entry.find("{http://www.w3.org/2005/Atom}link")
            if link_node is not None:
                link = (link_node.attrib.get("href") or "").strip()
            if not title and not summary:
                continue
            items.append(
                {
                    "title": title or source_name,
                    "summary": self._clean_text(summary)[:220],
                    "source": source_name,
                    "published_at": published_at,
                    "link": link,
                }
            )
        return items

    def _clean_text(self, value: str) -> str:
        cleaned = value.replace("<![CDATA[", "").replace("]]>", "")
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        return " ".join(cleaned.split())
