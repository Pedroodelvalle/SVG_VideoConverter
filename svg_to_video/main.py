from converter import SVGVideoConverter
import os
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import traceback

app = FastAPI()

BASE_OUTPUT = "/app/generated_videos"  # mesmo usado no converter

class SVGInput(BaseModel):
    svg_content: str

@app.post("/generate-video/")
async def generate_video(svg_input: SVGInput):
    try:
        if not svg_input.svg_content:
            raise ValueError("Campo 'svg_content' está vazio ou ausente")

        converter = SVGVideoConverter(svg_input.svg_content)
        await converter.embed_images_as_base64()
        output_path = await converter.create_video()

        if not os.path.isfile(output_path):
            raise RuntimeError(f"Arquivo MP4 não gerado: {output_path}")

        filename = os.path.basename(output_path)

        return {
            "message": "Vídeo criado com sucesso",
            "video_url": f"/videos/{filename}"
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao gerar vídeo: {str(e)}")

@app.get("/videos/{filename}")
async def stream_video(filename: str):
    file_path = os.path.join(BASE_OUTPUT, filename)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Vídeo não encontrado.")

    return StreamingResponse(open(file_path, "rb"), media_type="video/mp4")