"""
Web-Scraper – URL-basierte Dokumenten-Ingestion.

Fetcht HTML-Seiten, extrahiert strukturierten Text,
erzeugt eine Markdown-Datei und speist sie in die Ingestion-Pipeline.

On-Premise: Laeuft komplett lokal, keine Cloud-APIs.
Proxy-kompatibel fuer Komm.ONE-Umgebung.
"""
import asyncio
import logging
import re
import tempfile
from pathlib import Path
from typing import AsyncGenerator
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings

logger = logging.getLogger(__name__)

# Max. Groesse einer gescrapten Seite (10 MB)
MAX_SCRAPE_SIZE = 10 * 1024 * 1024

# Erlaubte Content-Types
ALLOWED_TYPES = {
    "text/html", "text/plain", "text/markdown",
    "application/pdf", "application/xhtml+xml",
}


class WebScraper:
    """Asynchroner Web-Scraper mit Proxy-Support."""

    def __init__(self):
        proxy_url = settings.http_proxy or settings.https_proxy or None
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            max_redirects=5,
            proxy=proxy_url,
            headers={
                "User-Agent": "AgentischerDocStore/2.0 (Komm.ONE; On-Premise)",
                "Accept": "text/html,application/xhtml+xml,text/plain,application/pdf",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
            },
        )

    async def close(self):
        await self._client.aclose()

    async def scrape_url(
        self,
        url: str,
        store_dir: Path,
    ) -> AsyncGenerator[dict, None]:
        """
        URL scrapen und als Datei speichern.
        Gibt Fortschritts-Updates als Generator zurueck (fuer SSE).

        Returns: file_path, original_filename, content_type
        """
        parsed = urlparse(url)
        if not parsed.scheme in ("http", "https"):
            yield {"step": "error", "progress": 0, "message": f"Ungueltiges URL-Schema: {parsed.scheme}"}
            return

        yield {"step": "fetch", "progress": 0.1, "message": f"Lade {parsed.netloc}..."}

        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            yield {"step": "error", "progress": 0, "message": f"HTTP-Fehler: {e.response.status_code}"}
            return
        except httpx.ConnectError:
            yield {"step": "error", "progress": 0, "message": f"Verbindung fehlgeschlagen: {parsed.netloc}"}
            return
        except httpx.TimeoutException:
            yield {"step": "error", "progress": 0, "message": f"Timeout: {parsed.netloc}"}
            return
        except Exception as e:
            logger.error(f"Scrape-Fehler {url}: {e}")
            yield {"step": "error", "progress": 0, "message": f"Fehler: {str(e)[:200]}"}
            return

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        content_length = len(response.content)

        if content_length > MAX_SCRAPE_SIZE:
            yield {"step": "error", "progress": 0, "message": f"Zu gross: {content_length // 1024 // 1024} MB (max 10 MB)"}
            return

        yield {"step": "parse", "progress": 0.3, "message": f"Typ: {content_type}, {content_length // 1024} KB"}

        # ─── PDF: direkt speichern ───
        if "pdf" in content_type:
            filename = _safe_filename(parsed.path, "pdf") or "scraped_document.pdf"
            file_path = store_dir / filename
            file_path.write_bytes(response.content)
            yield {
                "step": "done", "progress": 1.0,
                "message": f"PDF gespeichert: {filename}",
                "file_path": str(file_path),
                "filename": filename,
            }
            return

        # ─── HTML: Text extrahieren und als Markdown speichern ───
        if "html" in content_type or "xhtml" in content_type:
            yield {"step": "extract", "progress": 0.5, "message": "HTML wird analysiert..."}

            text = response.text
            markdown = self._html_to_markdown(text, url)

            if len(markdown.strip()) < 50:
                yield {"step": "error", "progress": 0, "message": "Kein extrahierbarer Text auf der Seite"}
                return

            filename = _safe_filename(parsed.path, "md") or "scraped_page.md"
            file_path = store_dir / filename
            file_path.write_text(markdown, encoding="utf-8")

            word_count = len(markdown.split())
            yield {
                "step": "done", "progress": 1.0,
                "message": f"Extrahiert: {filename} ({word_count} Woerter)",
                "file_path": str(file_path),
                "filename": filename,
            }
            return

        # ─── Plaintext / Markdown: direkt speichern ───
        if "text" in content_type:
            filename = _safe_filename(parsed.path, "txt") or "scraped_text.txt"
            file_path = store_dir / filename
            file_path.write_text(response.text, encoding="utf-8")
            yield {
                "step": "done", "progress": 1.0,
                "message": f"Text gespeichert: {filename}",
                "file_path": str(file_path),
                "filename": filename,
            }
            return

        yield {"step": "error", "progress": 0, "message": f"Nicht unterstuetzter Content-Type: {content_type}"}

    def _html_to_markdown(self, html: str, source_url: str) -> str:
        """HTML zu strukturiertem Markdown konvertieren."""
        soup = BeautifulSoup(html, "lxml")

        # Entferne Script, Style, Nav, Footer
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        parts = [f"# {soup.title.string.strip()}" if soup.title and soup.title.string else "# Gescrapte Seite"]
        parts.append(f"\n> Quelle: {source_url}\n")

        # Meta-Description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            parts.append(f"*{meta_desc['content'].strip()}*\n")

        # Hauptinhalt extrahieren
        main = soup.find("main") or soup.find("article") or soup.find("body")
        if not main:
            return "\n".join(parts) + "\n\nKein Hauptinhalt gefunden."

        for element in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "blockquote", "pre"]):
            text = element.get_text(separator=" ", strip=True)
            if not text or len(text) < 3:
                continue

            tag = element.name
            if tag == "h1":
                parts.append(f"\n## {text}")
            elif tag == "h2":
                parts.append(f"\n### {text}")
            elif tag in ("h3", "h4"):
                parts.append(f"\n#### {text}")
            elif tag == "li":
                parts.append(f"- {text}")
            elif tag == "blockquote":
                parts.append(f"> {text}")
            elif tag == "pre":
                parts.append(f"```\n{text}\n```")
            elif tag in ("td", "th"):
                parts.append(f"| {text} ")
            else:
                if len(text) > 10:
                    parts.append(f"\n{text}")

        # Tabellen erkennen
        for table in main.find_all("table"):
            rows = table.find_all("tr")
            if rows:
                parts.append("\n")
                for row in rows[:30]:  # Max 30 Zeilen
                    cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                    if any(cells):
                        parts.append("| " + " | ".join(cells) + " |")
                parts.append("")

        result = "\n".join(parts)
        # Bereinigung
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()


def _safe_filename(path: str, default_ext: str) -> str:
    """Sicheren Dateinamen aus URL-Pfad ableiten."""
    name = Path(path).stem if path else ""
    name = re.sub(r"[^\w\-]", "_", name).strip("_")
    if not name or len(name) < 2:
        return ""
    return f"{name[:80]}.{default_ext}"


# Singleton
scraper = WebScraper()
