import base64   
import mimetypes   
import os   
import re  
import shlex
import subprocess   
import tempfile   
import atexit
from urllib.parse import urlparse      
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET 
import cairosvg
import requests
from PIL import Image, ImageDraw, ImageFilter


class SVGVideoConverter:

    def __init__(self,svg_content: str):
        self.svg_content = svg_content
        self.processed_svg = None
        self.temp_files = []
        atexit.register(self._cleanup_temp_files) 

    def embed_images_as_base64(self):
        try:
            namespaces = {
                'svg': 'http://www.w3.org/2000/svg',
                'xlink': 'http://www.w3.org/1999/xlink'
            }

            root = ET.fromstring(self.svg_content)

            image_elements = root.findall('.//svg:image', namespaces)
            with ThreadPoolExecutor(max_workers=2) as executor:
                executor.map(lambda elem: self._replace_image_href_with_base64(elem,namespaces), image_elements)  

            self.processed_svg = ET.tostring(root, encoding='utf-8', method='xml').decode('utf-8')
            return self
        
        except Exception as e:
            raise RuntimeError(f"Erro ao processar SVG: {str(e)}")
        
    def _replace_image_href_with_base64(self, elem, namespaces):
        url = self._get_href_attribute(elem, namespaces)

        base64_data = None
        if url and url.startswith('http'):
            print(f"🔗 Convertendo imagem: {url}")
            base64_data = self._url_to_base64(url)

        if base64_data and base64_data.startswith("data:image/"):
                if '{{{xlink}}}href'.format(**namespaces) in elem.attrib:
                    elem.set('{{{xlink}}}href'.format(**namespaces), base64_data)
                else:
                    elem.set('href', base64_data)
    
    def _get_href_attribute(self, elem, namespaces):
        return elem.get('{{{xlink}}}href'.format(**namespaces)) or elem.get('href')
    
    def _url_to_base64(self, url: str) -> str:
        try:
            response = requests.get(
                url,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10,
                stream=True
            )
            response.raise_for_status()

            if int(response.headers.get('Content-Length', 0)) > 10 * 1024 * 1024:
                print(f"Imagem muito grande (>10MB): {url}")
                return None
            
            content_type = response.headers.get('Content-Type', '')
            mime_type = content_type.split(';')[0] if ';' in content_type else content_type

            if not mime_type.startswith('image/'):
                mime_type = mimetypes.guess_type(url) [0] or 'image/jpeg'

            encoded = base64.b64encode(response.content).decode('utf-8')

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

    def create_video(self, video_url: str = None, output_path: str = "output.mp4", scale: float = 1.5):
        
        if not self.processed_svg:
            raise RuntimeError("SVG não processado. Execute embed_images_as_base64() primeiro.")
        
        try: 
            if not video_url:
                video_url = self._extract_video_url()

            video_path = self._download_video(video_url)

            png_path = self._render_svg_to_png(scale=scale)

            self._ffmpeg_processing(png_path, video_path, output_path)

            print (f"✅ Vídeo finalizado: {output_path}")

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
        
    def _render_svg_to_png(self, scale: float = 1.5) -> str:
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
        
    def _ffmpeg_processing(self, png_path: str, video_path: str, output_path: str):
        x, y, width, height, rx, ry = self._get_video_overlay_position()

        filter_complex = f"""
        [1:v]scale={width}:{height}:force_original_aspect_ratio=increase, crop={width}:{height}[vid];
        [0:v][vid]overlay={x}:{y}:shortest=1
    """.replace("\n", "").strip()
            
        cmd = [
            'ffmpeg', '-y',
            '-threads', '1',
            '-loglevel', 'error',
            '-loop', '1', '-r', '30', '-i', png_path,
            '-i', video_path,
            '-filter_complex', filter_complex,
            '-c:a', 'aac', '-b:a', '128k',
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-tune', 'fastdecode',
            '-movflags', '+faststart',
            '-crf', '23',
            '-f', 'mp4',
            output_path
        ]

        print("🧠 Comando FFmpeg sendo executado:")
        print(shlex.join(cmd))
    
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
            print("✅ FFmpeg STDOUT:", result.stdout)
            print("✅ FFmpeg STDERR:", result.stderr)
        except subprocess.TimeoutExpired as e:
            print("❌ FFmpeg atingiu o tempo limite de execução.")
            raise RuntimeError("FFmpeg Timeout: o processo excedeu o tempo limite configurado.")
        except subprocess.CalledProcessError as e:
            print("❌ FFmpeg falhou")
            print("❌ Comando:", shlex.join(e.cmd))
            print("❌ FFmpeg STDOUT:", e.stdout)
            print("❌ FFmpeg STDERR:", e.stderr)
            raise RuntimeError(f"Erro FFmpeg: {e.stderr}")            
            
        
    def _cleanup_temp_files(self):
            for path in self.temp_files: 
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except Exception as e:
                    print(f"⚠️ Erro ao limpar arquivo temporário '{path}':{str(e)}")