from converter import SVGVideoConverter, upload_to_supabase
import os
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import traceback
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

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

        # ✅ Upload para Supabase
        public_url = upload_to_supabase(output_path, filename)

        return {
            "message": "Vídeo criado com sucesso",
            "video_url": public_url
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao gerar vídeo: {str(e)}")