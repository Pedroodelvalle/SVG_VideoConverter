import base64
import re
import requests
import os
import mimetypes
import cairosvg
import time
from io import BytesIO
from typing import List, Dict, Tuple
import hashlib
from functools import lru_cache
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_IMAGES_BUCKET", "posts_images")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_png_to_supabase(file_path: str, filename: str) -> str:
    with open(file_path, "rb") as f:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=filename,
            file=f,
            file_options={"content-type": "image/png"}
        )
    public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
    return public_url

_svg_png_cache = {}
MAX_CACHE_SIZE = 100
TIMEOUT_SECONDS = 10  
SCALE_FACTOR = 1.0   
FALLBACK_SIZE = (1080, 1350)  
CACHE_FOLDER = "/app/generated_cache"
os.makedirs(CACHE_FOLDER, exist_ok=True)

def convert_svg_images_to_base64_and_save(svg_content: str, output_folder: str) -> List[Dict[str, str]]:
    os.makedirs(output_folder, exist_ok=True)

    svg_elements = re.findall(r'(<svg[\s\S]*?</svg>)', svg_content)
    if not svg_elements:
        return []
    
    processed_files = []

    for idx, svg in enumerate(svg_elements):
        try:
            processed_svg = _process_svg_images(svg)
            processed_svg = _ensure_xlink_namespace(processed_svg)

            svg_hash = hash_svg(processed_svg)
            cached = _svg_png_cache.get(svg_hash)
            if cached and time.time() - cached["timestamp"] <= 600:  # 10 minutos
                png_path = cached["path"]
            else:
                png_path = _save_svg_and_convert(processed_svg, svg_hash, output_folder)
                _svg_png_cache[svg_hash] = {
                    "url": png_path,  
                    "timestamp": time.time()
                }

                if len(_svg_png_cache) > MAX_CACHE_SIZE:
                    _svg_png_cache.pop(next(iter(_svg_png_cache)))

            processed_files.append({"svg": processed_svg, "png": _svg_png_cache[svg_hash]["url"]})
        except Exception as e:
            print(f"[ERRO] Falha no SVG #{idx+1}: {str(e)}")
            continue
    
    # Clean up expired cache entries before returning
    purge_expired_cache()
    return processed_files

def _process_svg_images(svg: str) -> str:
    pattern = r'(<image\b[\s\S]*?(?:xlink:href|href)\s*=\s*["\'])(https?://[^"\']+)(["\'])'

    def replace_with_base64(match: re.Match) -> str:
        prefix, url, suffix = match.groups()
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
        except Exception as e:
            print(f"[AVISO] Falha ao baixar imagem: {url} | Erro: {str(e)}")
            return match.group(0)

        mime_type = _get_mime_type(response, url)
        base64_data = base64.b64encode(response.content).decode("utf-8")
        return f'{prefix}data:{mime_type};base64,{base64_data}{suffix}'

    return re.sub(pattern, replace_with_base64, svg, flags=re.IGNORECASE)

def _get_mime_type(response: requests.Response, url: str) -> str:
    mime_type = response.headers.get("Content-Type", "")
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(url.split("?")[0])
    return (mime_type or "image/png").split(';')[0]

def _ensure_xlink_namespace(svg: str) -> str:
    if 'xmlns:xlink' not in svg:
        svg = re.sub(r'<svg\b', r'<svg xmlns:xlink="http://www.w3.org/1999/xlink"', svg, count=1)
    if 'xmlns="' not in svg:
        svg = re.sub(r'<svg\b', r'<svg xmlns="http://www.w3.org/2000/svg"', svg, count=1)
    return svg


def _save_svg_and_convert(processed_svg: str, svg_hash: str, output_folder: str) ->  str:
    png_filename = f"{svg_hash}.png"
    png_path = os.path.join(output_folder, png_filename)

    width, height = _extract_svg_dimensions(processed_svg)

    cairosvg.svg2png(
        file_obj=BytesIO(processed_svg.encode()),
        write_to=png_path,
        output_width=width,
        output_height=height,
        scale=SCALE_FACTOR,
        unsafe=True
    )

    png_path = f"generated_images/{svg_hash}/converted_1.png"
    png_url = upload_png_to_supabase(png_path, f"{svg_hash}.png")

    return png_url




def _extract_svg_dimensions(svg: str) -> Tuple[int, int]:
    width_match = re.search(r'width\s*=\s*["\']([\d.]+)(?:px)?["\']', svg, re.IGNORECASE)
    height_match = re.search(r'height\s*=\s*["\']([\d.]+)(?:px)?["\']', svg, re.IGNORECASE)

    if width_match and height_match:
        return int(float(width_match.group(1))), int(float(height_match.group(1)))

    viewbox_match = re.search(r'viewBox\s*=\s*["\']\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)\s*["\']', svg)
    if viewbox_match:
        return int(float(viewbox_match.group(1))), int(float(viewbox_match.group(2)))

    print("[INFO] Dimensões não detectadas, usando fallback.")
    return FALLBACK_SIZE

def hash_svg(svg: str) -> str:
    return hashlib.sha256(svg.encode("utf-8")).hexdigest()

def cleanup_cache_folder(path=CACHE_FOLDER, max_files=200):
    files = sorted(os.listdir(path), key=lambda x: os.path.getctime(os.path.join(path, x)))
    while len(files) > max_files:
        os.remove(os.path.join(path, files.pop(0)))

def purge_expired_cache(ttl=600):
    now = time.time()
    expired_keys = [k for k, v in _svg_png_cache.items() if now - v["timestamp"] > ttl]

    for key in expired_keys:
        try:
            pass
        except Exception as e:
            print(f"[AVISO] Falha ao remover PNG expirado: {e}")
        _svg_png_cache.pop(key)