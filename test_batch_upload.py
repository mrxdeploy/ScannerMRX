import urllib.request
import urllib.parse
import json
import io
import os
import random

# Generate a dummy image
def create_dummy_image(color):
    from PIL import Image
    img = Image.new('RGB', (100, 100), color=color)
    byte_io = io.BytesIO()
    img.save(byte_io, 'JPEG')
    byte_io.seek(0)
    return byte_io.read()

def upload_multiple():
    url = "http://localhost:5000/dataset/upload-multiple"
    
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    # Body construction manually because urllib is verbose
    body = io.BytesIO()
    
    # Classification field
    body.write(f"--{boundary}\r\n".encode())
    body.write('Content-Disposition: form-data; name="classification"\r\n\r\n'.encode())
    body.write('BATCH_TEST\r\n'.encode())
    
    # Add 5 images
    colors = ['red', 'green', 'blue', 'yellow', 'purple']
    for i, color in enumerate(colors):
        filename = f"test_{color}.jpg"
        img_data = create_dummy_image(color)
        
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="images"; filename="{filename}"\r\n'.encode())
        body.write('Content-Type: image/jpeg\r\n\r\n'.encode())
        body.write(img_data)
        body.write('\r\n'.encode())
        
    body.write(f"--{boundary}--\r\n".encode())
    body_data = body.getvalue()
    
    req = urllib.request.Request(url, data=body_data)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    
    print("Uploading 5 images batch...")
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(json.dumps(result, indent=2))
            if result['success']:
                print("Batch upload successful!")
            else:
                print("Batch upload reported failure.")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Ensure PIL is installed via python check, but it should be
    upload_multiple()
