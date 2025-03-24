from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
from fastapi.responses import FileResponse
import os
from converter import convert_svg_images_to_base64_and_save, CACHE_FOLDER as BASE_OUTPUT

app = FastAPI()

class SVGInput(BaseModel):
    svg_content: str


@app.post("/generate-png")
def generate_png(data: SVGInput) -> List[Dict[str, str]]:
    try:
        output_folder = BASE_OUTPUT

        result = convert_svg_images_to_base64_and_save(data.svg_content, output_folder)

        if not result:
            raise HTTPException(status_code=400, detail="Nenhum SVG válido foi processado.")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/images/{filename}")
def get_png(filename: str):
    file_path = os.path.join(BASE_OUTPUT, filename)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Imagem não encontrada")

    return FileResponse(file_path, media_type="image/png")
