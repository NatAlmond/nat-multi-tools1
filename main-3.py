"""
Nat-Multi Tools v4 — FastAPI backend
API keys via environment only. Never hardcode.
"""
import os, uuid, json, re, hashlib, time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
import httpx

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

DOWNLOAD_DIR = Path("/tmp/downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Nat-Multi Tools", version="4.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def env(k: str, d: str = "") -> str:
    return os.environ.get(k, d).strip()

# ---------- Models ----------
class DownloadRequest(BaseModel):
    url: str
    type: str = "video"
    quality: str = "best"

class ChatRequest(BaseModel):
    model: str = "groq"
    messages: List[dict]

class ImageRequest(BaseModel):
    model: str = "nano-banana"
    prompt: str

# ---------- Frontend ----------
@app.get("/", response_class=HTMLResponse)
def home():
    for name in ("index.html",):
        p = Path(__file__).parent / name
        if p.exists():
            return HTMLResponse(p.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>index.html missing — upload index.html to repo root</h1>", status_code=404)

@app.get("/health")
def health():
    return {"status": "ok", "version": "4.0.0", "ytdlp": HAS_YTDLP}

@app.get("/banner.gif")
@app.get("/banner1.gif")
@app.get("/banner2.gif")
@app.get("/banner3.gif")
def serve_banner(request: Request):
    name = request.url.path.lstrip("/")
    for base in (Path(__file__).parent, Path(__file__).parent / "public"):
        p = base / name
        if p.exists():
            return FileResponse(p, media_type="image/gif")
        # fallback single banner
        p2 = base / "banner.gif"
        if p2.exists():
            return FileResponse(p2, media_type="image/gif")
    raise HTTPException(404, "banner not found")

# ---------- Download ----------
@app.post("/download")
def download(req: DownloadRequest):
    if not HAS_YTDLP:
        raise HTTPException(500, "yt-dlp tidak terpasang")
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL tidak valid")
    low = req.url.lower()
    if "spotify.com" in low:
        raise HTTPException(400, "Spotify tidak didukung (DRM)")
    # YouTube hint — frontend should gate as premium; backend still allows
    file_id = str(uuid.uuid4())[:8]
    outtmpl = str(DOWNLOAD_DIR / f"{file_id}.%(ext)s")
    if req.type == "audio":
        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
            "quiet": True, "no_warnings": True, "noplaylist": True,
        }
    else:
        fmt = {
            "best": "best[ext=mp4]/best",
            "720": "best[height<=720][ext=mp4]/best",
            "480": "best[height<=480][ext=mp4]/best",
            "360": "best[height<=360][ext=mp4]/best",
        }.get(req.quality, "best[ext=mp4]/best")
        opts = {"format": fmt, "outtmpl": outtmpl, "quiet": True, "no_warnings": True, "noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            title = info.get("title", "download")
            downloaded = next(DOWNLOAD_DIR.glob(f"{file_id}.*"), None)
            if not downloaded:
                raise Exception("File tidak ditemukan setelah unduhan")
            safe = "".join(c for c in title if c.isalnum() or c in " -_")[:60].strip() or "download"
            final = DOWNLOAD_DIR / f"{safe}{downloaded.suffix}"
            n = 1
            while final.exists():
                final = DOWNLOAD_DIR / f"{safe}_{n}{downloaded.suffix}"
                n += 1
            downloaded.rename(final)
            return {"status": "success", "filename": final.name, "download_url": f"/file/{final.name}", "title": title}
    except Exception as e:
        msg = str(e)
        lowm = msg.lower()
        if "sign in" in lowm or "not a bot" in lowm or "cookies" in lowm:
            msg = "YouTube memblokir server cloud. Coba TikTok/IG/FB atau platform lain."
        raise HTTPException(500, msg)

@app.get("/file/{filename}")
def get_file(filename: str):
    if ".." in filename or "/" in filename:
        raise HTTPException(400, "Invalid")
    path = DOWNLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File tidak ditemukan")
    return FileResponse(path, filename=filename, media_type="application/octet-stream")

# ---------- Comic (Sanka multi-source + fallbacks) ----------
SANKA = "https://www.sankavollerei.com"
SANKA_WEB = "https://www.sankavollerei.web.id"

# free sources that work well on Sanka
COMIC_FREE = ["komiku", "kiryuu", "komikstation", "westmanga", "mangakita", "bacakomik"]
COMIC_PREMIUM = ["shinigami", "manhwadesu", "omega"]  # treated as premium in UI

@app.get("/comic/search")
async def comic_search(source: str = "all", q: str = "", genre: str = ""):
    items = []
    sources = COMIC_FREE if source == "all" else [source]
    if source in COMIC_PREMIUM:
        sources = [source]
    try:
        async with httpx.AsyncClient(timeout=22.0, follow_redirects=True) as client:
            for src in sources[:4]:
                try:
                    if q:
                        urls = [
                            f"{SANKA}/comic/{src}/search/{q}",
                            f"{SANKA_WEB}/comic/{src}/search/{q}",
                        ]
                    else:
                        urls = [
                            f"{SANKA}/comic/{src}/home",
                            f"{SANKA}/comic/{src}/latest",
                            f"{SANKA_WEB}/comic/{src}/home",
                        ]
                    for url in urls:
                        r = await client.get(url)
                        if r.status_code != 200:
                            continue
                        data = r.json() if "application/json" in r.headers.get("content-type", "") else {}
                        raw = (
                            data.get("data") or data.get("comics") or data.get("manga")
                            or data.get("results") or data.get("list") or []
                        )
                        if isinstance(raw, dict):
                            raw = raw.get("list") or raw.get("items") or raw.get("manga") or []
                        for it in (raw if isinstance(raw, list) else [])[:12]:
                            title = it.get("title") or it.get("name") or "?"
                            thumb = it.get("thumb") or it.get("image") or it.get("cover") or it.get("thumbnail") or ""
                            cid = it.get("slug") or it.get("endpoint") or it.get("id") or it.get("href") or ""
                            if isinstance(cid, str) and cid.startswith("http"):
                                cid = cid.rstrip("/").split("/")[-1]
                            g = it.get("type") or it.get("genre") or ""
                            items.append({
                                "title": title,
                                "thumb": thumb,
                                "id": cid,
                                "source": src,
                                "label": "PROJECT" if src in ("kiryuu", "westmanga") else ("MANHWA" if "manhwa" in str(g).lower() else "KOMIK"),
                                "chapter": it.get("chapter") or it.get("latest") or it.get("chapter_latest") or "",
                            })
                        if items:
                            break
                except Exception:
                    continue
            # genre client-side filter if provided
            if genre:
                g = genre.lower()
                items = [x for x in items if g in (x.get("title") or "").lower() or g in str(x.get("label", "")).lower()]
    except Exception as e:
        raise HTTPException(502, f"Comic source error: {e}")
    # dedupe by title
    seen = set()
    unique = []
    for it in items:
        key = (it["title"] or "").lower()[:40]
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    return {"items": unique[:30]}

@app.get("/comic/detail")
async def comic_detail(source: str = "komiku", id: str = ""):
    chapters, title, synopsis, thumb, genres = [], id, "", "", []
    try:
        async with httpx.AsyncClient(timeout=22.0, follow_redirects=True) as client:
            for base in (SANKA, SANKA_WEB):
                r = await client.get(f"{base}/comic/{source}/manga/{id}")
                if r.status_code != 200:
                    continue
                data = r.json() if "json" in r.headers.get("content-type", "") else {}
                d = data.get("data") or data
                title = d.get("title") or title
                synopsis = d.get("synopsis") or d.get("sinopsis") or d.get("description") or d.get("desc") or ""
                thumb = d.get("thumb") or d.get("image") or d.get("cover") or ""
                genres = d.get("genres") or d.get("genre") or []
                if isinstance(genres, str):
                    genres = [g.strip() for g in genres.split(",")]
                for ch in (d.get("chapters") or d.get("chapter") or [])[:100]:
                    chapters.append({
                        "title": ch.get("title") or ch.get("chapter") or str(ch.get("number", "Chapter")),
                        "id": ch.get("slug") or ch.get("endpoint") or ch.get("id") or "",
                    })
                if chapters:
                    break
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"title": title, "chapters": chapters, "synopsis": synopsis if isinstance(synopsis, str) else "", "thumb": thumb, "genres": genres if isinstance(genres, list) else []}

@app.get("/comic/chapter")
async def comic_chapter(source: str = "komiku", id: str = ""):
    images = []
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for base in (SANKA, SANKA_WEB):
                r = await client.get(f"{base}/comic/{source}/chapter/{id}")
                if r.status_code != 200:
                    continue
                data = r.json() if "json" in r.headers.get("content-type", "") else {}
                d = data.get("data") or data
                images = d.get("images") or d.get("image") or d.get("pages") or []
                if images and isinstance(images[0], dict):
                    images = [x.get("url") or x.get("src") or "" for x in images]
                if images:
                    break
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"images": [i for i in images if i]}

@app.get("/comic/genres")
async def comic_genres():
    # static useful Indo genres — filter applied on search results + title
    return {"genres": [
        "Action", "Adventure", "Comedy", "Drama", "Fantasy", "Horror",
        "Romance", "School", "Sci-Fi", "Slice of Life", "Supernatural",
        "Martial Arts", "Manhwa", "Manhua", "Seinen", "Shounen"
    ]}

# ---------- Anime ----------
WAJIK = "https://wajik-anime-api.vercel.app"
SANKA_ANIME = "https://www.sankavollerei.com"

@app.get("/anime/search")
async def anime_search(source: str = "all", q: str = ""):
    items = []
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            targets = []
            if source in ("all", "otakudesu"):
                targets.append(("otakudesu", WAJIK))
            if source in ("all", "anoboy"):
                targets.append(("anoboy", SANKA_ANIME))
            if source == "samehadaku":
                targets.append(("samehadaku", WAJIK))
            for src, base in targets:
                try:
                    if src in ("otakudesu", "samehadaku"):
                        path = f"/{src}/search" if q else f"/{src}/ongoing"
                        r = await client.get(base + path, params={"q": q, "page": 1} if q else {"page": 1})
                    else:
                        path = f"/anime/anoboy/search/{q}" if q else "/anime/anoboy/home"
                        r = await client.get(base + path)
                    if r.status_code != 200:
                        continue
                    data = r.json()
                    raw = (
                        data.get("data", {}).get("animeList")
                        or data.get("data", {}).get("anime_list")
                        or data.get("animeList")
                        or data.get("data")
                        or data.get("results")
                        or []
                    )
                    if isinstance(raw, dict):
                        raw = raw.get("animeList") or raw.get("list") or []
                    for it in (raw if isinstance(raw, list) else [])[:16]:
                        items.append({
                            "title": it.get("title") or it.get("anime_name") or it.get("name") or "?",
                            "thumb": it.get("poster") or it.get("thumbnail") or it.get("image") or it.get("thumb") or "",
                            "id": it.get("animeId") or it.get("slug") or it.get("id") or it.get("endpoint") or "",
                            "source": src,
                        })
                except Exception:
                    continue
    except Exception as e:
        raise HTTPException(502, f"Anime error: {e}")
    seen, unique = set(), []
    for it in items:
        k = (it["title"] or "").lower()[:40]
        if k in seen:
            continue
        seen.add(k)
        unique.append(it)
    return {"items": unique[:28]}

@app.get("/anime/detail")
async def anime_detail(source: str = "otakudesu", id: str = ""):
    episodes, title, synopsis, thumb, genres = [], id, "", "", []
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            if source in ("otakudesu", "samehadaku"):
                r = await client.get(f"{WAJIK}/{source}/anime/{id}")
                data = r.json() if r.status_code == 200 else {}
                d = data.get("data") or data
                title = d.get("title") or title
                synopsis = d.get("synopsis") or d.get("sinopsis") or d.get("description") or ""
                thumb = d.get("poster") or d.get("thumbnail") or d.get("image") or ""
                genres = d.get("genres") or d.get("genre") or []
                if isinstance(genres, str):
                    genres = [g.strip() for g in genres.split(",")]
                elif genres and isinstance(genres[0], dict):
                    genres = [g.get("name") or g.get("title") or str(g) for g in genres]
                for ep in (d.get("episodeList") or d.get("episodes") or d.get("episode_list") or [])[:100]:
                    episodes.append({
                        "title": ep.get("title") or ep.get("episode") or f"Episode {ep.get('number','')}",
                        "id": ep.get("episodeId") or ep.get("slug") or ep.get("id") or ep.get("endpoint") or "",
                    })
            else:
                r = await client.get(f"{SANKA_ANIME}/anime/anoboy/anime/{id}")
                data = r.json() if r.status_code == 200 else {}
                d = data.get("data") or data
                title = d.get("title") or title
                synopsis = d.get("synopsis") or d.get("sinopsis") or ""
                thumb = d.get("thumb") or d.get("image") or ""
                for ep in (d.get("episodes") or d.get("episode") or [])[:100]:
                    episodes.append({"title": ep.get("title") or ep.get("name") or "Episode", "id": ep.get("slug") or ep.get("id") or ""})
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"title": title, "episodes": episodes, "synopsis": synopsis if isinstance(synopsis, str) else "", "thumb": thumb, "genres": genres if isinstance(genres, list) else []}

@app.get("/anime/episode")
async def anime_episode(source: str = "otakudesu", id: str = ""):
    stream_url, streams = "", []
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if source in ("otakudesu", "samehadaku"):
                r = await client.get(f"{WAJIK}/{source}/episode/{id}")
                data = r.json() if r.status_code == 200 else {}
                d = data.get("data") or data
                stream_url = d.get("stream_url") or d.get("streamUrl") or d.get("iframe") or d.get("embed") or d.get("defaultStreamUrl") or ""
                if not stream_url and isinstance(d.get("stream"), dict):
                    stream_url = d["stream"].get("url") or ""
                for key in ("streamList", "streams", "download"):
                    arr = d.get(key)
                    if isinstance(arr, list):
                        for s in arr:
                            if isinstance(s, dict):
                                u = s.get("url") or s.get("link") or ""
                                if u:
                                    streams.append(u)
                            elif isinstance(s, str):
                                streams.append(s)
            else:
                r = await client.get(f"{SANKA_ANIME}/anime/anoboy/episode/{id}")
                data = r.json() if r.status_code == 200 else {}
                d = data.get("data") or data
                stream_url = d.get("stream") or d.get("stream_url") or d.get("iframe") or ""
                if isinstance(stream_url, list):
                    streams = stream_url
                    stream_url = stream_url[0] if stream_url else ""
        if not stream_url and streams:
            stream_url = streams[0]
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"stream_url": stream_url, "streams": streams, "embed": stream_url}

# ---------- Novel (wbnovel scrape) ----------
@app.get("/novel/search")
async def novel_search(q: str = ""):
    items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            r = await client.get("https://wbnovel.com/", params={"s": q, "post_type": "wp-manga"} if q else None)
            html = r.text
            seen = set()
            for m in re.finditer(r'href="(https://wbnovel\.com/nv/([^/"]+)/)"[^>]*>([^<]{3,90})</a>', html):
                slug, title = m.group(2), m.group(3).strip()
                if slug in seen or "chapter" in slug.lower():
                    continue
                seen.add(slug)
                items.append({"title": title or slug.replace("-", " ").title(), "thumb": "", "id": slug, "source": "wbnovel"})
            if not items:
                for m in re.finditer(r'href="https://wbnovel\.com/nv/([^/"]+)/"', html):
                    slug = m.group(1)
                    if slug in seen or "chapter" in slug:
                        continue
                    seen.add(slug)
                    items.append({"title": slug.replace("-", " ").title(), "thumb": "", "id": slug, "source": "wbnovel"})
    except Exception as e:
        raise HTTPException(502, f"Novel error: {e}")
    return {"items": items[:24]}

@app.get("/novel/detail")
async def novel_detail(id: str = ""):
    if not id:
        raise HTTPException(400, "id kosong")
    chapters, title, synopsis = [], id.replace("-", " ").title(), ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"}
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers) as client:
            r = await client.get(f"https://wbnovel.com/nv/{id}/")
            html = r.text
            m = re.search(r"<h1[^>]*>([^<]+)", html)
            if m:
                title = m.group(1).strip()
            for pat in [r'class="[^"]*summary[^"]*"[^>]*>(.*?)</div>', r'class="[^"]*description[^"]*"[^>]*>(.*?)</div>']:
                sm = re.search(pat, html, re.I | re.S)
                if sm:
                    synopsis = re.sub(r"<[^>]+>", " ", sm.group(1))
                    synopsis = re.sub(r"\s+", " ", synopsis).strip()
                    if len(synopsis) > 40:
                        break
            for m in re.finditer(r'href="(https://wbnovel\.com/nv/[^"]+/chapter-[^"]+)"[^>]*>([^<]+)', html):
                chapters.append({"title": m.group(2).strip(), "id": m.group(1).replace("https://wbnovel.com/nv/", "").rstrip("/")})
            if not chapters:
                for m in re.finditer(r'href="(/nv/[^"]+/chapter-[^"]+)"[^>]*>([^<]+)', html):
                    chapters.append({"title": m.group(2).strip(), "id": m.group(1).lstrip("/").replace("nv/", "").rstrip("/")})
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"title": title, "synopsis": synopsis, "chapters": chapters[:150], "genres": []}

@app.get("/novel/chapter")
async def novel_chapter(id: str = ""):
    if not id:
        raise HTTPException(400, "id kosong")
    content, title = "", ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"}
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=headers) as client:
            url = id if id.startswith("http") else f"https://wbnovel.com/nv/{id}/"
            r = await client.get(url)
            html = r.text
            m = re.search(r"<h1[^>]*>([^<]+)", html)
            if m:
                title = m.group(1).strip()
            for pat in [r'class="[^"]*reading-content[^"]*"[^>]*>(.*?)</div>\s*</div>', r'class="text-left"[^>]*>(.*?)</div>', r'class="entry-content"[^>]*>(.*?)</div>']:
                cm = re.search(pat, html, re.I | re.S)
                if cm:
                    raw = re.sub(r"<script[^>]*>.*?</script>", "", cm.group(1), flags=re.S)
                    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
                    raw = re.sub(r"</p>", "\n\n", raw, flags=re.I)
                    raw = re.sub(r"<[^>]+>", "", raw)
                    content = re.sub(r"\n{3,}", "\n\n", raw).strip()
                    if len(content) > 100:
                        break
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"title": title, "content": content}

# ---------- GIF (Gifukai — NO API KEY) ----------
GIFUKAI_ACTIONS = [
    "hug", "kiss", "pat", "cry", "sleep", "pout", "blush", "dance",
    "happy", "angry", "wave", "slap", "punch", "bite", "cuddle", "highfive",
    "bonk", "smile", "wink", "shrug", "facepalm", "nom", "poke", "stare",
]

@app.get("/gif/search")
async def gif_search(q: str = "hug"):
    q = (q or "hug").strip().lower()[:40]
    # map common words to gifukai actions
    alias = {
        "anime": "hug", "love": "kiss", "sad": "cry", "happy": "happy",
        "angry": "angry", "mad": "angry", "dance": "dance", "sleep": "sleep",
        "wave": "wave", "hi": "wave", "hello": "wave", "punch": "punch",
        "slap": "slap", "bite": "bite", "cuddle": "cuddle", "blush": "blush",
        "reaction": "shrug", "meme": "facepalm", "cartoon": "dance",
    }
    action = alias.get(q, q if q in GIFUKAI_ACTIONS else "hug")
    items = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            # fetch several randoms for a "search" grid
            for _ in range(12):
                r = await client.get(f"https://api.gifukai.com/v1/{action}")
                if r.status_code != 200:
                    continue
                data = r.json()
                url = data.get("url") or ""
                if url:
                    items.append({
                        "url": url,
                        "preview": url,
                        "title": f"{data.get('action', action)} · {data.get('anime', 'Anime')}",
                    })
            # also try related actions if few results
            if len(items) < 6:
                for a in GIFUKAI_ACTIONS:
                    if a == action:
                        continue
                    r = await client.get(f"https://api.gifukai.com/v1/{a}")
                    if r.status_code == 200:
                        data = r.json()
                        url = data.get("url") or ""
                        if url:
                            items.append({"url": url, "preview": url, "title": f"{a} · {data.get('anime','')}"})
                    if len(items) >= 16:
                        break
    except Exception as e:
        raise HTTPException(502, f"GIF error: {e}")
    return {"items": items[:20], "query": action, "provider": "gifukai"}

@app.get("/gif/actions")
async def gif_actions():
    return {"actions": GIFUKAI_ACTIONS}

# ---------- AI Chat ----------
@app.post("/ai/chat")
async def ai_chat(req: ChatRequest):
    messages = req.messages or []
    if not messages:
        raise HTTPException(400, "Pesan kosong")

    if req.model == "groq":
        key = env("GROQ_API_KEY")
        if not key:
            raise HTTPException(503, "GROQ_API_KEY belum diset di Environment Variables")
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": messages,
                    "temperature": 0.7,
                },
            )
            if r.status_code != 200:
                raise HTTPException(502, f"Groq error: {r.text[:200]}")
            data = r.json()
            return {"reply": data["choices"][0]["message"]["content"]}

    if req.model in ("gemini", "gemini-3.6", "gemini-3.8", "gemini-flash"):
        key = env("GEMINI_API_KEY")
        if not key:
            raise HTTPException(503, "GEMINI_API_KEY belum diset")
        # Prefer Gemini 3.6 Flash, fallback 2.5
        models_try = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
        contents = []
        for m in messages:
            role = "user" if m.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
        last_err = ""
        async with httpx.AsyncClient(timeout=60.0) as client:
            for model in models_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                r = await client.post(url, json={"contents": contents})
                if r.status_code == 200:
                    data = r.json()
                    try:
                        reply = data["candidates"][0]["content"]["parts"][0]["text"]
                        return {"reply": reply, "model_used": model}
                    except Exception:
                        last_err = json.dumps(data)[:300]
                else:
                    last_err = r.text[:200]
        raise HTTPException(502, f"Gemini error: {last_err}")

    raise HTTPException(400, "Model tidak dikenal")

# ---------- AI Image ----------
@app.post("/ai/image")
async def ai_image(req: ImageRequest):
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(400, "Prompt kosong")
    key = env("GEMINI_API_KEY")
    if not key:
        raise HTTPException(503, "GEMINI_API_KEY belum diset")

    # Nano Banana 2.1 preferred, fallbacks
    models_try = [
        "gemini-nano-banana-2.1",
        "gemini-2.5-flash-image",
        "gemini-2.0-flash-exp-image-generation",
    ]
    last_err = ""
    async with httpx.AsyncClient(timeout=90.0) as client:
        for model in models_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
            }
            r = await client.post(url, json=payload)
            if r.status_code == 200:
                data = r.json()
                try:
                    parts = data["candidates"][0]["content"]["parts"]
                    for p in parts:
                        if "inlineData" in p:
                            b64 = p["inlineData"]["data"]
                            mime = p["inlineData"].get("mimeType", "image/png")
                            return {
                                "b64": f"data:{mime};base64,{b64}",
                                "image_url": f"data:{mime};base64,{b64}",
                                "model_used": model,
                            }
                except Exception:
                    last_err = "no image in response"
            else:
                last_err = r.text[:250]
    raise HTTPException(502, f"Image gen gagal: {last_err}. Pastikan key mendukung image generation.")

# ---------- Drama / Movie (LK21 mirrors) ----------
@app.get("/movie/search")
async def movie_search(q: str = "", type: str = "movie"):
    """Movie/Drama via unofficial LK21 mirrors only (no TMDB)."""
    items = []
    try:
        async with httpx.AsyncClient(timeout=18.0, follow_redirects=True) as client:
            lk21_bases = [
                "https://lk21-api-omega.vercel.app",
                "https://lk21-api.cyclic.app",
            ]
            for base in lk21_bases:
                try:
                    if type == "drama":
                        path = f"/search/{q}" if q else "/series"
                    else:
                        path = f"/search/{q}" if q else "/movies"
                    r = await client.get(base + path)
                    if r.status_code != 200:
                        alt = f"/api/v1/search?q={q}" if q else "/api/v1/latest"
                        r = await client.get(base + alt)
                    if r.status_code != 200:
                        continue
                    data = r.json()
                    raw = data if isinstance(data, list) else (
                        data.get("data") or data.get("movies") or data.get("results")
                        or data.get("series") or data.get("list") or []
                    )
                    if isinstance(raw, dict):
                        raw = raw.get("movies") or raw.get("list") or raw.get("data") or []
                    for it in (raw if isinstance(raw, list) else [])[:20]:
                        title = it.get("title") or it.get("name") or it.get("movieId") or "?"
                        thumb = it.get("poster") or it.get("thumbnail") or it.get("image") or it.get("thumb") or ""
                        mid = it.get("_id") or it.get("id") or it.get("movieId") or it.get("slug") or title
                        items.append({
                            "title": title,
                            "thumb": thumb,
                            "id": str(mid),
                            "overview": it.get("synopsis") or it.get("overview") or it.get("description") or "",
                            "year": str(it.get("year") or it.get("release") or "")[:4],
                            "type": type,
                            "source": "lk21",
                        })
                    if items:
                        break
                except Exception:
                    continue
    except Exception as e:
        raise HTTPException(502, str(e))
    if not items:
        return {"items": [], "hint": "Mirror LK21 sedang down / kosong. Coba lagi nanti."}
    return {"items": items}


# ---------- Safelink resolve (follow redirects only) ----------
@app.get("/safelink")
async def safelink(url: str = ""):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL tidak valid")
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            final = str(r.url)
            return {"original": url, "final": final, "status": r.status_code}
    except Exception as e:
        raise HTTPException(502, str(e))

# ---------- Admin verify (server-side hash — tighter than pure localStorage) ----------
ADMIN_HASH = hashlib.sha256(b"PEANUTSBUTTERCUP").hexdigest()

@app.post("/admin/verify")
async def admin_verify(request: Request):
    body = await request.json()
    code = (body.get("code") or "").strip()
    if hashlib.sha256(code.encode()).hexdigest() == ADMIN_HASH:
        # return short-lived token (not cryptographic security, just harder casual bypass)
        token = hashlib.sha256(f"{code}:{int(time.time()//3600)}".encode()).hexdigest()[:24]
        return {"ok": True, "token": token, "role": "admin"}
    raise HTTPException(403, "Kode salah")
