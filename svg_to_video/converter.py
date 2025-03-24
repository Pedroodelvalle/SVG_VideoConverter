import base64   
import mimetypes   
import os   
import re  
import shlex
import subprocess   
import tempfile   
import atexit
from PIL import Image
import io
from urllib.parse import urlparse      
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET 
import cairosvg
import requests
from PIL import Image, ImageDraw, ImageFilter
import hashlib
import time
import asyncio
import aiohttp
from supabase import create_client
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "videos")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_to_supabase(file_path: str, filename: str) -> str:
    with open(file_path, "rb") as f:
        supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=filename,
            file=f,
            file_options={"content-type": "video/mp4"}
        )
    public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)
    return public_url

_video_cache = {}
MAX_CACHE_SIZE = 100
TTL_SECONDS = 600  # 10 minutos
CACHE_FOLDER = "/app/generated_videos"

os.makedirs(CACHE_FOLDER, exist_ok=True)

def _hash_svg(svg: str) -> str:
    return hashlib.sha256(svg.encode("utf-8")).hexdigest()

class SVGVideoConverter:

    def __init__(self,svg_content: str):
        self.svg_content = svg_content
        self.processed_svg = None
        self.temp_files = []
        atexit.register(self._cleanup_temp_files) 

    def _normalize_svg_for_hashing(self, svg: str) -> str:
        try:
            namespaces = {
                'svg': 'http://www.w3.org/2000/svg',
                'xlink': 'http://www.w3.org/1999/xlink'
            }

            root = ET.fromstring(svg)
            image_elements = root.findall('.//svg:image', namespaces)

            for elem in image_elements:
                if '{{{xlink}}}href'.format(**namespaces) in elem.attrib:
                    elem.set('{{{xlink}}}href'.format(**namespaces), 'NORMALIZED')
                elif 'href' in elem.attrib:
                    elem.set('href', 'NORMALIZED')

            return ET.tostring(root, encoding='utf-8', method='xml').decode('utf-8')

        except Exception as e:
            print(f"Erro ao normalizar SVG para hash: {str(e)}")
            return svg  # fallback

    async def embed_images_as_base64(self):
        try:
            namespaces = {
                'svg': 'http://www.w3.org/2000/svg',
                'xlink': 'http://www.w3.org/1999/xlink'
            }

            root = ET.fromstring(self.svg_content)

            image_elements = root.findall('.//svg:image', namespaces)
            tasks = [self._replace_image_href_with_base64_async(elem, namespaces) for elem in image_elements]
            await asyncio.gather(*tasks)


            self.processed_svg = ET.tostring(root, encoding='utf-8', method='xml').decode('utf-8')
            return self
        
        except Exception as e:
            raise RuntimeError(f"Erro ao processar SVG: {str(e)}")
        
    async def _replace_image_href_with_base64_async(self, elem, namespaces):
        url = self._get_href_attribute(elem, namespaces)
        if url and url.startswith('http'):
            print(f"🔗 Convertendo imagem: {url}")
            base64_data = await self._url_to_base64_async(url)

            if base64_data and base64_data.startswith("data:image/"):
                if '{{{xlink}}}href'.format(**namespaces) in elem.attrib:
                    elem.set('{{{xlink}}}href'.format(**namespaces), base64_data)
                else:
                    elem.set('href', base64_data)
    
    def _get_href_attribute(self, elem, namespaces):
        return elem.get('{{{xlink}}}href'.format(**namespaces)) or elem.get('href')
    
    async def _url_to_base64_async(self, url: str) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        print(f"Erro ao baixar imagem: {response.status}")
                        return None
                    
                    if int(response.headers.get('Content-Length', 0)) > 10 * 1024 * 1024:
                        print(f"Imagem muito grande (>10MB): {url}")
                        return None

                    content = await response.read()
                    content_type = response.headers.get('Content-Type', '')
                    mime_type = content_type.split(';')[0] if ';' in content_type else content_type
                    if not mime_type.startswith('image/'):
                        mime_type = mimetypes.guess_type(url)[0] or 'image/jpeg'
                    
                    encoded = base64.b64encode(content).decode('utf-8')
                    return f"data:{mime_type};base64,{encoded}"

        except Exception as e:
            print(f"Erro ao baixar imagem {url}: {str(e)}")
            return None
        
    def _extract_video_url(self) -> str: 
        root = ET.fromstring(self.processed_svg)

        video_rect = root.find(".//*[@id='video-area']")

        if video_rect is None:
            for elem in root.iter():
                id_attr = elem.get("id", "")
                if "video" in id_attr.lower():
                    video_rect = elem
                    break

        if video_rect is None:
            for elem in root.iter():
                if elem.get("video_url") or elem.get("data-video-url"):
                    video_rect = elem
                    break

        if video_rect is None:                
            raise RuntimeError("Elemento com id='video-area' ou outro elemento relacionado a vídeo não encontrado no SVG.")
        
        video_url = video_rect.get("video_url") or video_rect.get("data-video-url")
        if not video_url:
            raise RuntimeError("Atributo 'video_url ou 'data-video-url' não encontrado no elemento com id='video-area'.")
                               
        return video_url       

    async def create_video(self, video_url: str = None, output_path: str = "output.mp4", scale: float = 1.2):
        
        normalized_svg = self._normalize_svg_for_hashing(self.svg_content)
        svg_hash = _hash_svg(normalized_svg)

        if not self.processed_svg:
            await self.embed_images_as_base64()

        output_path = os.path.join(CACHE_FOLDER, f"{svg_hash}.mp4")

        cached = _video_cache.get(svg_hash)
        if cached and time.time() - cached["timestamp"] <= TTL_SECONDS and os.path.isfile(cached["path"]):
            print("♻️ Reutilizando vídeo em cache")
            return cached["path"]
        
        try: 
            if not video_url:
                video_url = self._extract_video_url()

            video_path = self._download_video(video_url)

            png_path = self._render_svg_to_png(scale=scale)
            await self._ffmpeg_processing(png_path, video_path, output_path)

            print (f"✅ Vídeo finalizado: {output_path}")

            _video_cache[svg_hash] = {
                "path": output_path,
                "timestamp": time.time()
            }

            self._purge_expired_cache()

            return output_path

        finally:
            self._cleanup_temp_files()


                                
    def _download_video(self, url: str) -> str:
        try: 
            response = requests.get(
                url, 
                headers={'User-Agent': 'Mozilla/5.0'},
                stream=True,
                timeout=20
            )
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('video/'):
                raise RuntimeError(f"Tipo de conteúdo inválido: {content_type}")
            
            content_length = int(response.headers.get('Content-Length', 0))
            if content_length > 100 * 1024 * 1024:   #100MB
                raise RuntimeError(f"Vídeo muito grande: {content_length / (1024 * 1024):.2f}MB")
            
            temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            self.temp_files.append(temp_video.name)

            with open(temp_video.name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=5 * 1024 * 1024):
                    if chunk:
                        temp_video.write(chunk)

            temp_video.close()
            return temp_video.name
        
        except Exception as e:
            raise RuntimeError(f"Falha no Download do vídeo: {str(e)}")
        
    def _render_svg_to_png(self, scale: float = 1.2) -> str:
        try:
            width, height = self._get_svg_dimensions()

            temp_png = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            self.temp_files.append(temp_png.name)

            cairosvg.svg2png(
                bytestring=self.processed_svg.encode('utf-8'),
                write_to=temp_png.name,
                output_width=int(width * scale),
                output_height=int(height * scale)
            )
            return temp_png.name
        
        except Exception as e:
            raise RuntimeError(f"Erro ao renderizar SVG para PNG: {str(e)}")
        
    def _get_svg_dimensions(self) -> tuple:
        root = ET.fromstring(self.processed_svg)

        width_str = root.get('width', '1080').replace('px', '').replace(',', '.')
        height_str = root.get('height', '1920').replace('px', '').replace(',', '.')

        try:
            width = int(float(width_str))
            height = int(float(height_str))
            return width, height

        except: 
            viewbox = root.get('viewBox', '0 0 1080 1920').split()
            width = int(float(viewbox[2].replace(',', '.')))
            height = int(float(viewbox[3].replace(',', '.')))
            return width, height 
        
    def _get_video_overlay_position(self, scale: float = 1.5) -> tuple:
        root = ET.fromstring(self.processed_svg)
        video_rect = root.find(".//*[@id='video-area']")

        if video_rect is None:
            raise RuntimeError("Elemento com id='video-area' não encontrado no SVG")
        
        def clean(value: str, fallback: str = "0") -> float:
            return float(value.replace("px", "").strip()) if value else float(fallback)

        x = int(clean(video_rect.get("x")) * scale)
        y = int(clean(video_rect.get("y")) * scale)
        width = int(clean(video_rect.get("width", "850")) * scale)
        height = int(clean(video_rect.get("height", "600")) * scale)
        rx = int(clean(video_rect.get("rx")))
        ry = int(clean(video_rect.get("ry")))

        print("📐 Extraindo posição do vídeo:")
        print("x:", x, "y:", y, "width:", width, "height:", height, "rx:", rx, "ry:", ry)
        return x, y, width, height, rx, ry
        
    async def _ffmpeg_processing(self, png_path: str, video_path: str, output_path: str):
        x, y, width, height, rx, ry = self._get_video_overlay_position()

        filter_complex = f"""
        [1:v]scale={width}:{height}:force_original_aspect_ratio=increase, crop={width}:{height}[vid];
        [0:v][vid]overlay={x}:{y}:shortest=1
    """.replace("\n", "").strip()
            
        cmd = [
            'ffmpeg', '-y',
            '-threads', '1',
            '-loglevel', 'error',
            '-loop', '1', '-r', '24', '-i', png_path,
            '-i', video_path,
            '-filter_complex', filter_complex,
            '-c:a', 'aac', '-b:a', '128k',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'fastdecode',
            '-movflags', '+faststart',
            '-crf', '28',
            '-f', 'mp4',
            output_path
        ]

        print("🧠 Comando FFmpeg sendo executado:")
        print(shlex.join(cmd))
    
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            print("❌ FFmpeg falhou")
            print("❌ STDOUT:", stdout.decode())
            print("❌ STDERR:", stderr.decode())
            raise RuntimeError(f"Erro FFmpeg: {stderr.decode()}")
        else:
            print("✅ FFmpeg completado com sucesso.")
            print("✅ STDOUT:", stdout.decode())
        
    def _cleanup_temp_files(self):
            for path in self.temp_files: 
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except Exception as e:
                    print(f"⚠️ Erro ao limpar arquivo temporário '{path}':{str(e)}")

    def _purge_expired_cache(self):
        now = time.time()
        expired = [k for k, v in _video_cache.items() if now - v["timestamp"] > TTL_SECONDS]

        for key in expired:
            try:
                os.remove(_video_cache[key]["path"])
            except Exception as e:
                print(f"⚠️ Erro ao remover vídeo expirado '{key}': {str(e)}")
            _video_cache.pop(key)

        # Limite de tamanho
        while len(_video_cache) > MAX_CACHE_SIZE:
            oldest = next(iter(_video_cache))
            try:
                os.remove(_video_cache[oldest]["path"])
            except:
                pass
            _video_cache.pop(oldest)