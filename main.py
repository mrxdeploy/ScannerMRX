"""
MRX SCAN - Sistema de Classificacao de Sucata Eletronica
Scanner por camera e gestao de dataset usando OpenCLIP
Wrapper para DB-based Storage
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import Optional, List
from pathlib import Path
from contextlib import asynccontextmanager

from embedding_engine import get_engine, OFFICIAL_CLASSES
from database import init_db, get_db, ScanHistory

app = FastAPI(
    title="MRX SCAN",
    description="Sistema de classificacao de sucata eletronica por similaridade de imagem",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATASET_DIR = "dataset"
os.makedirs(DATASET_DIR, exist_ok=True)
os.makedirs("embeddings", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
# Removed static mount for images, replaced by dynamic endpoint
# app.mount("/images", StaticFiles(directory=DATASET_DIR), name="images")

@app.on_event("startup")
async def startup_event():
    """Initialize the database and embedding engine on startup"""
    import os
    # Skip init_db if tables were already created by create_tables.py
    if not os.getenv("SKIP_DB_INIT"):
        print("Initializing database...")
        init_db()
        print("Database initialized!")
    else:
        print("Database already initialized by startup script")
    print("Initializing MRX SCAN embedding engine...")
    try:
        engine = get_engine()
        print("Syncing initial data from repo...")
        engine.sync_initial_data()
        print("MRX SCAN ready!")
    except Exception as e:
        print(f"Startup Error: {e}")
        # raise e # Don't raise to let us see the output

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main scanner interface"""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/images/{class_name}/{filename}")
async def get_image(class_name: str, filename: str):
    """Serve image dynamically from database"""
    try:
        engine = get_engine()
        image_data = engine.get_image_data(class_name, filename)
        
        if not image_data:
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Determine media type based on extension
        import mimetypes
        media_type, _ = mimetypes.guess_type(filename)
        media_type = media_type or "image/jpeg"
        
        return Response(content=image_data, media_type=media_type)
    except Exception as e:
        print(f"Error serving image: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/scan")
async def scan_image(image: UploadFile = File(...)):
    """
    Scan an image and classify it
    Returns: classification, confidence score, and top 3 matches
    """
    try:
        contents = await image.read()
        
        if not contents:
            raise HTTPException(status_code=400, detail="Empty image file")
        
        engine = get_engine()
        result = engine.classify_image(contents)
        
        return JSONResponse(content=result)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/dataset/upload")
async def upload_to_dataset(
    image: UploadFile = File(...),
    classification: str = Form(...)
):
    """
    Upload a new image to a specific classification in the dataset
    This updates the embeddings automatically
    """
    try:
        contents = await image.read()
        
        if not contents:
            raise HTTPException(status_code=400, detail="Empty image file")
        
        engine = get_engine()
        saved_path = engine.add_image_to_class(
            classification,
            contents,
            image.filename or "image.jpg"
        )
        
        return JSONResponse(content={
            "success": True,
            "message": f"Image added to {classification}",
            "path": saved_path
        })
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/dataset/upload-multiple")
async def upload_multiple_images(
    images: List[UploadFile] = File(...),
    classification: str = Form(...)
):
    """
    Upload multiple images to a specific classification
    Optimized for batch processing
    """
    try:
        engine = get_engine()
        
        batch = []
        for image in images:
            contents = await image.read()
            if contents:
                batch.append((image.filename or "image.jpg", contents))
        
        if not batch:
             raise HTTPException(status_code=400, detail="No valid images received")

        saved_paths = engine.add_multiple_images_to_class(classification, batch)
        
        return JSONResponse(content={
            "success": True,
            "message": f"{len(saved_paths)} images added to {classification}",
            "paths": saved_paths
        })
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dataset/classes")
async def get_classes():
    """
    Get all available classifications with image counts
    """
    try:
        engine = get_engine()
        classes = engine.get_class_info()
        
        return JSONResponse(content={
            "classes": classes,
            "total_classes": len(classes)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/dataset/create")
async def create_classification(name: str = Form(...)):
    """
    Create a new classification folder
    """
    try:
        engine = get_engine()
        success = engine.create_class(name)
        
        if not success:
            return JSONResponse(content={
                "success": False,
                "message": f"Classification '{name}' already exists or could not be created",
                "path": name
            }, status_code=400)
        
        return JSONResponse(content={
            "success": True,
            "message": f"Classification '{name}' created successfully",
            "path": name
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dataset/images/{class_name:path}")
async def get_class_images(class_name: str):
    """
    Get all images from a specific classification
    """
    try:
        engine = get_engine()
        matches = engine.image_paths_cache.get(class_name, [])
        
        images = []
        for match in matches:
            images.append({
                "filename": match["filename"],
                "path": match["path"]
            })
            
        return JSONResponse(content={
            "class_name": class_name,
            "images": images,
            "total": len(images)
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/images/{class_name}/{filename}")
async def get_image(class_name: str, filename: str):
    """
    Serve image directly from database
    """
    try:
        engine = get_engine()
        image_data = engine.get_image_data(class_name, filename)
        
        if not image_data:
            raise HTTPException(status_code=404, detail="Image not found")
            
        from fastapi.responses import Response
        import mimetypes
        
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "image/jpeg"
            
        return Response(content=image_data, media_type=content_type)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/dataset/capture-multiple")
async def capture_multiple_images(
    images: List[UploadFile] = File(...),
    classification: str = Form(...)
):
    """
    Upload multiple captured images from camera to a specific classification
    """
    try:
        import uuid
        from datetime import datetime
        
        engine = get_engine()
        batch = []
        
        for image in images:
            contents = await image.read()
            if contents:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_id = uuid.uuid4().hex[:8]
                filename = f"capture_{timestamp}_{unique_id}.jpg"
                batch.append((filename, contents))
                
        if not batch:
             raise HTTPException(status_code=400, detail="No valid images received")
             
        saved_paths = engine.add_multiple_images_to_class(classification, batch)
        
        return JSONResponse(content={
            "success": True,
            "message": f"{len(saved_paths)} imagens capturadas adicionadas a {classification}",
            "paths": saved_paths
        })
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/dataset/retrain")
async def retrain_dataset():
    """
    Retrain all embeddings (Reloads from DB)
    """
    try:
        engine = get_engine()
        engine._load_embeddings_from_db()
        
        return JSONResponse(content={
            "success": True,
            "message": "Embeddings reloaded from database"
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "model": "OpenCLIP ViT-B-32", "system": "MRX SCAN", "storage": "PostgreSQL"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
