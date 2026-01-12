"""
Embedding Engine Module for MRX SCAN - Electronic Scrap Classification
Uses OpenCLIP for image embedding generation and PostgreSQL for persistent storage
"""

import os
import numpy as np
from PIL import Image
import open_clip
import torch
from typing import List, Dict, Tuple, Optional
import json
from pathlib import Path
import io
from sqlalchemy.orm import Session
from database import get_session_local, DatasetImage, Embedding, Classification
from sqlalchemy import func

DATASET_DIR = "dataset"
EMBEDDINGS_DIR = "embeddings"

SIMILARITY_THRESHOLD = 0.60

OFFICIAL_CLASSES = [
    "HIGH GRADE",
    "MIDION GRADE",
    "MIDION GRADE 1 - MG 1",
    "MIDION GRADE 2 - MG 2",
    "LOW GRADE",
    "LOW",
    "DIVERSOS",
    "GARIMPOS",
    "MOAGEM",
    "HD"
]

class EmbeddingEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.preprocess = None
        # Cache for faster lookup (will be populated from DB)
        self.embeddings_cache: Dict[str, np.ndarray] = {}
        self.image_paths_cache: Dict[str, List[Dict]] = {} # List of dicts with id, filename
        
        self.db_session = get_session_local()()
        
        self._load_model()
        self._load_embeddings_from_db()
    
    def _load_model(self):
        """Load the OpenCLIP model for image embedding generation"""
        print("Loading OpenCLIP model...")
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            'ViT-B-32',
            pretrained='laion2b_s34b_b79k'
        )
        self.model = self.model.to(self.device)
        self.model.eval()
        print(f"Model loaded on {self.device}")
    
    def generate_embedding(self, image: Image.Image) -> np.ndarray:
        """Generate embedding vector for a single image"""
        with torch.no_grad():
            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
            embedding = self.model.encode_image(image_tensor)
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)
            return embedding.cpu().numpy().flatten()
    
    def generate_embedding_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        """Generate embedding from image bytes"""
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            return self.generate_embedding(image)
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise ValueError("Invalid image data")

    def _load_embeddings_from_db(self):
        """Load all embeddings from database into memory cache"""
        print("Loading embeddings from database...")
        
        # Reset caches
        self.embeddings_cache = {}
        self.image_paths_cache = {}
        
        try:
            # Load Embeddings
            embeddings_query = self.db_session.query(Embedding).all()
            for emb in embeddings_query:
                class_name = emb.classification
                embedding_vector = np.frombuffer(emb.embedding_data, dtype=np.float32)
                
                if class_name not in self.embeddings_cache:
                    self.embeddings_cache[class_name] = []
                
                self.embeddings_cache[class_name].append(embedding_vector)
            
            # Convert lists to numpy arrays
            for class_name in self.embeddings_cache:
                self.embeddings_cache[class_name] = np.array(self.embeddings_cache[class_name])
                
            self._rebuild_cache_from_images_table()
            
            print("Embeddings loaded from DB")
            
        except Exception as e:
            print(f"Error loading embeddings from DB: {e}")
            self.db_session.rollback()

    def _rebuild_cache_from_images_table(self):
        """Rebuild in-memory cache strictly from DatasetImage table to ensure consistency"""
        print("Rebuilding cache from DatasetImage table...")
        
        # We assume self.embeddings_cache matches self.image_paths_cache logic
        # But to be safe, let's sync efficiently.
        
        images_count_q = self.db_session.query(DatasetImage.classification, func.count(DatasetImage.id)).group_by(DatasetImage.classification).all()
        embeddings_count_q = self.db_session.query(Embedding.classification, func.count(Embedding.id)).group_by(Embedding.classification).all()
        
        img_counts = {c: n for c, n in images_count_q}
        emb_counts = {c: n for c, n in embeddings_count_q}
        
        # Also ensure all explicit classes exist in cache even if empty
        class_records = self.db_session.query(Classification).all()
        for c_rec in class_records:
            if c_rec.name not in self.image_paths_cache:
                self.image_paths_cache[c_rec.name] = []
            if c_rec.name not in self.embeddings_cache:
                self.embeddings_cache[c_rec.name] = np.array([])

        all_active_classes = set(list(img_counts.keys()) + list(emb_counts.keys()))
        
        for class_name in all_active_classes:
            i_count = img_counts.get(class_name, 0)
            e_count = emb_counts.get(class_name, 0)
            
            if i_count == 0:
                continue
                
            if i_count != e_count:
                print(f"Mismatch for {class_name}: {i_count} images vs {e_count} embeddings. Regenerating...")
                self._regenerate_class_embeddings_db(class_name)
            else:
                # Load from DB
                raw_embs = self.db_session.query(Embedding).filter_by(classification=class_name).order_by(Embedding.id).all()
                images = self.db_session.query(DatasetImage).filter_by(classification=class_name).order_by(DatasetImage.id).all()
                
                vectors = []
                for emb in raw_embs:
                    vectors.append(np.frombuffer(emb.embedding_data, dtype=np.float32))
                
                if vectors:
                    self.embeddings_cache[class_name] = np.array(vectors)
                    self.image_paths_cache[class_name] = [
                        {"id": img.id, "filename": img.filename, "path": f"/images/{class_name}/{img.filename}"}
                        for img in images
                    ]
                    
                    # Double check alignment length
                    if len(self.embeddings_cache[class_name]) != len(self.image_paths_cache[class_name]):
                         print(f"Alignment error for {class_name}, regenerating...")
                         self._regenerate_class_embeddings_db(class_name)

    def _regenerate_class_embeddings_db(self, class_name: str):
        """Regenerate embeddings for a class from DB images"""
        # Delete existing embeddings for this class
        self.db_session.query(Embedding).filter_by(classification=class_name).delete()
        self.db_session.commit()
        
        images = self.db_session.query(DatasetImage).filter_by(classification=class_name).order_by(DatasetImage.id).all()
        
        vectors = []
        paths = []
        new_embedding_records = []
        
        print(f"Regenerating {len(images)} embeddings for {class_name}...")
        
        for img in images:
            if not img.image_data:
                continue
                
            try:
                vec = self.generate_embedding_from_bytes(img.image_data)
                vectors.append(vec)
                paths.append({
                    "id": img.id, 
                    "filename": img.filename, 
                    "path": f"/images/{class_name}/{img.filename}"
                })
                
                # Create embedding record
                new_embedding_records.append(Embedding(
                    classification=class_name,
                    embedding_data=vec.tobytes()
                ))
            except Exception as e:
                print(f"Error processing image {img.id}: {e}")
        
        if new_embedding_records:
            self.db_session.add_all(new_embedding_records)
            self.db_session.commit()
            
            self.embeddings_cache[class_name] = np.array(vectors)
            self.image_paths_cache[class_name] = paths
            print(f"Regeneration complete for {class_name}")

    def generate_embeddings_batch(self, images: List[Image.Image]) -> np.ndarray:
        """Generate embeddings for a batch of images"""
        if not images:
            return np.array([])
            
        try:
            # Preprocess all images
            # self.preprocess return a tensor (C, H, W)
            # Stack to get (B, C, H, W)
            image_tensors = torch.stack([self.preprocess(img) for img in images]).to(self.device)
            
            with torch.no_grad():
                embeddings = self.model.encode_image(image_tensors)
                embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)
                return embeddings.cpu().numpy()
                
        except Exception as e:
            print(f"Error generating batch embeddings: {e}")
            raise e

    def create_class(self, class_name: str) -> bool:
        """Create a new classification in the database"""
        try:
            existing = self.db_session.query(Classification).filter_by(name=class_name).first()
            if existing:
                return False
            
            new_class = Classification(name=class_name)
            self.db_session.add(new_class)
            self.db_session.commit()
            
            # Initialize in cache
            if class_name not in self.embeddings_cache:
                self.embeddings_cache[class_name] = np.array([])
            if class_name not in self.image_paths_cache:
                self.image_paths_cache[class_name] = []
            
            return True
        except Exception as e:
            self.db_session.rollback()
            print(f"Error creating class {class_name}: {e}")
            raise e

    def add_multiple_images_to_class(self, class_name: str, images_list: List[Tuple[str, bytes]]) -> List[str]:
        """
        Batch add images to a class using batch inference.
        images_list: List of (filename, bytes)
        Returns list of saved paths
        """
        import uuid
        import re
        
        # Ensure class exists
        self.create_class(class_name)
        
        if not images_list:
            return []
            
        print(f"Processing batch of {len(images_list)} images for {class_name}...")
        
        saved_paths = []
        pil_images = []
        valid_filenames = []
        raw_contents = []
        
        # 1. Pre-process text/filenames and load PIL images
        for filename, content in images_list:
            try:
                # Sanitize filename
                safe_filename = os.path.basename(filename)
                safe_filename = re.sub(r'[^\w\-.]', '_', safe_filename)
                base_name = os.path.splitext(safe_filename)[0] or 'image'
                ext = os.path.splitext(safe_filename)[1] or '.jpg'
                if ext.lower() not in {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif'}:
                    ext = '.jpg'
                    
                unique_id = uuid.uuid4().hex[:8]
                new_filename = f"{base_name}_{unique_id}{ext}"
                
                img = Image.open(io.BytesIO(content)).convert("RGB")
                
                pil_images.append(img)
                valid_filenames.append(new_filename)
                raw_contents.append(content)
                
            except Exception as e:
                print(f"Skipping corrupt/invalid file {filename}: {e}")
        
        if not pil_images:
            return []

        # 2. Batch Inference
        try:
            print("Running batch inference...")
            embeddings_matrix = self.generate_embeddings_batch(pil_images)
            print("Inference complete.")
        except Exception as e:
            print(f"Bacth inference failed: {e}")
            raise e
            
        # 3. Create Records
        new_images_records = []
        new_embedding_records = []
        
        # Prepare cache updates (delay until success)
        cache_update_vectors = []
        cache_update_paths = []
        
        for i, new_filename in enumerate(valid_filenames):
            content = raw_contents[i]
            vec = embeddings_matrix[i] # NumPy array
            
            img_record = DatasetImage(
                filename=new_filename,
                classification=class_name,
                image_data=content,
                image_path=f"/images/{class_name}/{new_filename}" 
            )
            emb_record = Embedding(
                classification=class_name,
                embedding_data=vec.tobytes()
            )
            
            new_images_records.append(img_record)
            new_embedding_records.append(emb_record)
            saved_paths.append(img_record.image_path)
            
            cache_update_vectors.append(vec)
            cache_update_paths.append({
                "id": None, 
                "filename": new_filename,
                "path": img_record.image_path
            })

        # 4. Batch Insert
        if new_images_records:
            try:
                self.db_session.add_all(new_images_records)
                self.db_session.add_all(new_embedding_records)
                self.db_session.commit()
                print(f"Batch inserted {len(new_images_records)} records into DB.")
                
                # 5. Update Cache
                new_vectors_stacked = np.array(cache_update_vectors)
                
                if class_name not in self.embeddings_cache:
                    self.embeddings_cache[class_name] = new_vectors_stacked
                    self.image_paths_cache[class_name] = cache_update_paths
                else:
                    current_embs = self.embeddings_cache[class_name]
                    if len(current_embs) == 0:
                         self.embeddings_cache[class_name] = new_vectors_stacked
                    else:
                        self.embeddings_cache[class_name] = np.vstack([current_embs, new_vectors_stacked])
                    
                    self.image_paths_cache[class_name].extend(cache_update_paths)
                    
            except Exception as e:
                self.db_session.rollback()
                print(f"Batch insert failed DB transaction: {e}")
                raise e
                
        return saved_paths

    def add_image_to_class(self, class_name: str, image_bytes: bytes, filename: str) -> str:
        """Legacy wrapper for single image"""
        paths = self.add_multiple_images_to_class(class_name, [(filename, image_bytes)])
        return paths[0] if paths else ""
        
    def get_image_data(self, class_name: str, filename: str) -> Optional[bytes]:
        """Retrieve raw image bytes from DB"""
        img = self.db_session.query(DatasetImage).filter_by(
            classification=class_name, 
            filename=filename
        ).first()
        return img.image_data if img else None

    def sync_initial_data(self):
        """On startup, import files from local 'dataset' folder into DB if DB is empty"""
        if not os.path.exists(DATASET_DIR):
            return

        print("Checking for local files to import...")
        for class_name in os.listdir(DATASET_DIR):
            class_path = os.path.join(DATASET_DIR, class_name)
            if not os.path.isdir(class_path):
                continue
                
            # Create the class explicitly
            self.create_class(class_name)
                
            # Check if we already have images for this class in DB
            count = self.db_session.query(DatasetImage).filter_by(classification=class_name).count()
            if count > 0:
                continue # Already populated
            
            print(f"Importing local folder {class_name} to database...")
            batch = []
            valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif'}
            
            files = [f for f in os.listdir(class_path) if os.path.splitext(f)[1].lower() in valid_exts]
            
            for f in files:
                fpath = os.path.join(class_path, f)
                try:
                    with open(fpath, "rb") as file:
                        content = file.read()
                    batch.append((f, content))
                except Exception as e:
                    print(f"Error reading {f}: {e}")
            
            if batch:
                self.add_multiple_images_to_class(class_name, batch)
                print(f"Imported {len(batch)} images for {class_name}")

    def classify_image(self, image_bytes: bytes) -> Dict:
        """Classify an image and return results"""
        # (Same logic as before but using self.embeddings_cache which is now DB-backed)
        query_embedding = self.generate_embedding_from_bytes(image_bytes)
        
        all_classes = list(self.embeddings_cache.keys())
        class_scores = {}
        all_image_matches = []
        
        for class_name in all_classes:
            class_embeddings = self.embeddings_cache.get(class_name, np.array([]))
            class_paths = self.image_paths_cache.get(class_name, [])
            
            if len(class_embeddings) == 0:
                class_scores[class_name] = {
                    "avg_similarity": 0.0,
                    "max_similarity": 0.0,
                    "num_samples": 0
                }
                continue

            similarities = []
            # Calculate similarity
            # Vectorized operation
            sims = np.dot(class_embeddings, query_embedding) # (N,) result
            # Assuming query_embedding is already normalized (it is)
            # And class_embeddings are normalized (they are)
            
            # Note: numpy dict/arrays might have dimension issues if not careful
            if len(sims.shape) > 1:
                sims = sims.flatten()
                
            for i, sim in enumerate(sims):
                sim_val = float(sim)
                similarities.append(sim_val)
                
                if i < len(class_paths):
                    path_info = class_paths[i]
                    all_image_matches.append({
                        "classification": class_name,
                        "image_path": path_info.get("path", ""),
                        "similarity": round(sim_val * 100, 2)
                    })
            
            if similarities:
                class_scores[class_name] = {
                    "avg_similarity": float(np.mean(similarities)),
                    "max_similarity": float(np.max(similarities)),
                    "num_samples": len(similarities)
                }

        sorted_classes = sorted(
            class_scores.items(),
            key=lambda x: x[1]["avg_similarity"],
            reverse=True
        )
        
        top_class = sorted_classes[0][0] if sorted_classes else None
        top_score = sorted_classes[0][1]["avg_similarity"] if sorted_classes else 0.0
        
        sorted_image_matches = sorted(
            all_image_matches,
            key=lambda x: x["similarity"],
            reverse=True
        )
        
        reference_image = None
        if sorted_image_matches:
            best_match = sorted_image_matches[0]
            reference_image = {
                "image_path": best_match["image_path"],
                "classification": best_match["classification"],
                "similarity": best_match["similarity"]
            }
        
        top_3_images = sorted_image_matches[:3]
        
        top_3_classes = [
            {
                "classification": name,
                "similarity": round(scores["avg_similarity"] * 100, 2),
                "max_similarity": round(scores["max_similarity"] * 100, 2),
                "samples_count": scores["num_samples"]
            }
            for name, scores in sorted_classes[:3]
        ]
        
        has_samples = len(all_image_matches) > 0
        best_similarity = sorted_image_matches[0]["similarity"] / 100.0 if sorted_image_matches else 0.0
        
        if not has_samples:
            return {
                "classification": None,
                "similarity_score": 0.0,
                "reference_image": None,
                "top_matches": [],
                "top_3": [],
                "has_dataset": False,
                "status": "no_dataset",
                "message": "No images in dataset."
            }
        
        if best_similarity < SIMILARITY_THRESHOLD:
            return {
                "classification": None,
                "similarity_score": round(best_similarity * 100, 2),
                "reference_image": None,
                "top_matches": top_3_images,
                "top_3": top_3_classes,
                "has_dataset": True,
                "status": "no_match",
                "message": "No match found above threshold."
            }
        
        return {
            "classification": top_class,
            "similarity_score": round(top_score * 100, 2),
            "reference_image": reference_image,
            "top_matches": top_3_images,
            "top_3": top_3_classes,
            "has_dataset": True,
            "status": "match",
            "message": "Classification successful"
        }
    
    def get_class_info(self) -> List[Dict]:
        """Get information about all classes and their image counts from DB"""
        
        # In DB-backed mode, we should query the Classification table plus counts
        # But we already have in-memory chache synced on load.
        # Let's verify against DB for robustness or just use cache.
        # Using cache for speed.
        
        # However, ensure we include classes with 0 images.
        all_keys = sorted(list(set(list(self.image_paths_cache.keys()) + list(self.embeddings_cache.keys()))))
        
        result = []
        for k in all_keys:
            count = len(self.image_paths_cache.get(k, []))
            result.append({
                "name": k,
                "image_count": count,
                "has_embeddings": count > 0
            })
        return result

engine = None

def get_engine() -> EmbeddingEngine:
    """Get or create the embedding engine singleton"""
    global engine
    if engine is None:
        engine = EmbeddingEngine()
    return engine
