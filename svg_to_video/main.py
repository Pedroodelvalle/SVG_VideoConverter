from converter import SVGVideoConverter
import os
import uuid
import traceback
from datetime import datetime
import threading
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


app = FastAPI()

class SVGInput(BaseModel):
    svg_code: str

def schedule_file_deletion(file_path: str, delay: int = 3600):
    def delete_file():
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print (f"Arquivo {file_path} removido após 1 hora.")
        except Exception as e: 
            print(f"Erro ao remover arquivo {file_path}: {str(e)}")

    timer = threading.Timer(delay, delete_file)
    timer.start()

@app.post("/generate-video/")
async def generate_video(svg_input: SVGInput):
    try:
        svg_code = svg_input.svg_code
        if not svg_code:
            raise ValueError("Campo 'svg' vazio ou ausente")
        
        filename= f"video_{uuid.uuid4().hex}.mp4"
        output_path = os.path.abspath(os.path.join("generated_videos", filename))
        os.makedirs("generated_videos", exist_ok=True)

        
        converter = SVGVideoConverter(svg_code)
        converter.embed_images_as_base64()
        converter.create_video(output_path=output_path)

        if not os.path.exists(output_path):
            raise RuntimeError(f"Arquivo não foi gerado: {output_path}")
        else:
            print("Arquivo gerado com sucesso e presente em disco:", output_path)

        schedule_file_deletion(output_path, delay=3600)

        return {
            "message": "Vídeo criado com sucesso",
            "download_url": f"http://localhost:8000/videos/{filename}"
        }
    
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao gerar vídeo: {str(e)}")
    
@app.get("/videos/{filename}")
async def get_video(filename: str):
    file_path = os.path.join("generated_videos", filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Vídeo não encontrado.")
    
    return FileResponse(path=file_path, filename=filename, media_type="video/mp4")