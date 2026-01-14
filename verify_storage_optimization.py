import os
import sys
import io
import numpy as np
from PIL import Image
from unittest.mock import MagicMock, patch

# Set env var BEFORE importing database/embedding_engine
os.environ["DATABASE_URL"] = "sqlite:///./test_storage.db"

# Mock open_clip to avoid heavy model loading
sys.modules["open_clip"] = MagicMock()
sys.modules["torch"] = MagicMock()
sys.modules["torch.cuda"] = MagicMock()
sys.modules["torch.cuda.is_available"] = MagicMock(return_value=False)

# Now import
from database import init_db, get_session_local, DatasetImage
from embedding_engine import EmbeddingEngine

def verify_storage():
    print("Setting up test database...")
    if os.path.exists("test_storage.db"):
        os.remove("test_storage.db")
    
    init_db()
    
    # Patch the engine to skip model loading and real inference
    with patch.object(EmbeddingEngine, '_load_model', return_value=None), \
         patch.object(EmbeddingEngine, 'generate_embeddings_batch') as mock_gen:
        
        # Setup mock return for embedding generation (batch size 1, 512 dim)
        mock_gen.return_value = np.random.rand(1, 512).astype(np.float32)
        
        engine = EmbeddingEngine()
        
        # Generate Large Image (5MB+)
        print("Generating large dummy image...")
        img = Image.new('RGB', (3000, 3000), color='blue')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        original_size = buf.tell()
        buf.seek(0)
        print(f"Original Input Size: {original_size / 1024 / 1024:.2f} MB")
        
        # Upload
        print("Uploading to 'TEST_CLASS'...")
        engine.add_multiple_images_to_class("TEST_CLASS", [("test_large_image.jpg", buf.getvalue())])
        
        # Check DB
        session = get_session_local()()
        db_img = session.query(DatasetImage).first()
        
        stored_size = len(db_img.image_data)
        print(f"Stored Size in DB: {stored_size / 1024:.2f} KB")
        
        if stored_size > 500 * 1024:
            print("FAILURE: Stored image is larger than 500KB")
            sys.exit(1)
        else:
            print("SUCCESS: Image stored efficiently")
            print(f"Compression Ratio: {original_size / stored_size:.1f}x")

if __name__ == "__main__":
    verify_storage()
