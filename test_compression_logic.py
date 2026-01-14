import io
from PIL import Image
import os

def test_compression():
    # Create a large dummy image (4000x3000) ~ 36MB in RGBA
    print("Generating large dummy image (4000x3000)...")
    img = Image.new('RGB', (4000, 3000), color = 'red')
    
    # Save as high quality JPEG to simulate user upload
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=95)
    original_size = buffer.tell()
    buffer.seek(0)
    
    print(f"Original Size: {original_size / 1024 / 1024:.2f} MB")
    
    # --- SIMULATE COMPRESSION LOGIC ---
    print("Applying compression...")
    MAX_DIMENSION = 1024
    
    # 1. Resize
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)
    
    # 2. Save optimized
    out_buffer = io.BytesIO()
    img.save(out_buffer, format='JPEG', quality=85, optimize=True)
    compressed_size = out_buffer.tell()
    
    print(f"Compressed Size: {compressed_size / 1024:.2f} KB")
    
    reduction = (1 - (compressed_size / original_size)) * 100
    print(f"Reduction: {reduction:.2f}%")
    
    if compressed_size > 500 * 1024: # Target under 500KB
        print("FAIL: Image still too large")
    else:
        print("PASS: Image successfully compressed")

if __name__ == "__main__":
    test_compression()
