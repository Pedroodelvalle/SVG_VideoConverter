import base64
import re
import requests
import os
import mimetypes
import cairosvg
from io import BytesIO
from typing import List, Dict, Tuple

TIMEOUT_SECONDS = 10  
SCALE_FACTOR = 2.0   
FALLBACK_SIZE = (1080, 1350)  

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

            svg_path, png_path = _save_svg_and_convert(processed_svg, output_folder, idx + 1)
            processed_files.append({"svg": svg_path, "png": png_path})
        except Exception as e:
            print(f"[ERRO] Falha no SVG #{idx+1}: {str(e)}")
            continue

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


def _save_svg_and_convert(processed_svg: str, output_folder: str, index: int) -> Tuple[str, str]:
    svg_filename = f"converted_{index}.svg"
    png_filename = f"converted_{index}.png"
    svg_path = os.path.join(output_folder, svg_filename)
    png_path = os.path.join(output_folder, png_filename)

    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(processed_svg)

    width, height = _extract_svg_dimensions(processed_svg)

    cairosvg.svg2png(
        file_obj=BytesIO(processed_svg.encode()),
        write_to=png_path,
        output_width=width,
        output_height=height,
        scale=SCALE_FACTOR,
        unsafe=True  # permite conteúdo externo embutido, importante para cloud
    )

    return svg_path, png_path


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

