import urllib.request
import urllib.parse
import json
import io
import os
import time

def result_print(test_name, success, msg=""):
    print(f"[{'PASS' if success else 'FAIL'}] {test_name}: {msg}")

def test_create_empty_class():
    print("\n--- Testing Empty Class Creation ---")
    try:
        class_name = f"EMPTY_{int(time.time())}"
        data = urllib.parse.urlencode({"name": class_name}).encode()
        req = urllib.request.Request("http://localhost:5000/dataset/create", data=data)
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            if res.get('success'):
                result_print('Create Class', True, f"Created {class_name}")
                return class_name
            else:
                result_print('Create Class', False, str(res))
                return None
    except Exception as e:
        result_print('Create Class', False, str(e))
        return None

def test_batch_upload(class_name):
    print(f"\n--- Testing Batch Upload to {class_name} ---")
    url = "http://localhost:5000/dataset/upload-multiple"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write('Content-Disposition: form-data; name="classification"\r\n\r\n'.encode())
    body.write(f'{class_name}\r\n'.encode())
    
    # Create 3 dummy red images
    for i in range(3):
        color = (255, 0, 0)
        from PIL import Image
        img = Image.new('RGB', (50, 50), color=color)
        byte_io = io.BytesIO()
        img.save(byte_io, 'JPEG')
        img_data = byte_io.getvalue()
        
        filename = f"red_{i}.jpg"
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="images"; filename="{filename}"\r\n'.encode())
        body.write('Content-Type: image/jpeg\r\n\r\n'.encode())
        body.write(img_data)
        body.write('\r\n'.encode())
        
    body.write(f"--{boundary}--\r\n".encode())
    
    req = urllib.request.Request(url, data=body.getvalue())
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    
    try:
        start_time = time.time()
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            duration = time.time() - start_time
            if res.get('success'):
                result_print('Batch Upload', True, f"Uploaded 3 images in {duration:.2f}s")
                return True
            else:
                result_print('Batch Upload', False, str(res))
                return False
    except Exception as e:
        result_print('Batch Upload', False, str(e))
        return False

def test_scan(class_name):
    print(f"\n--- Testing Scan against {class_name} ---")
    # Scan a red image
    url = "http://localhost:5000/scan"
    boundary = "----WebKitFormBoundaryScan"
    
    from PIL import Image
    img = Image.new('RGB', (50, 50), color=(255, 0, 0)) # Red
    byte_io = io.BytesIO()
    img.save(byte_io, 'JPEG')
    img_data = byte_io.getvalue()
    
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(f'Content-Disposition: form-data; name="image"; filename="scan_test.jpg"\r\n'.encode())
    body.write('Content-Type: image/jpeg\r\n\r\n'.encode())
    body.write(img_data)
    body.write('\r\n'.encode())
    body.write(f"--{boundary}--\r\n".encode())
    
    req = urllib.request.Request(url, data=body.getvalue())
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            print(json.dumps(res, indent=2))
            
            if res.get('classification') == class_name:
                result_print('Scan', True, f"Correctly classified as {class_name}")
            else:
                result_print('Scan', False, f"Expected {class_name}, got {res.get('classification')}")
    except Exception as e:
        result_print('Scan', False, str(e))

if __name__ == "__main__":
    c_name = test_create_empty_class()
    if c_name:
        if test_batch_upload(c_name):
            test_scan(c_name)
    
    # Test persistent empty class listing
    try:
        req = urllib.request.urlopen("http://localhost:5000/dataset/classes")
        data = json.loads(req.read().decode())
        names = [c['name'] for c in data['classes']]
        if c_name in names:
            result_print('List Classes', True, f"Found {c_name}")
    except Exception as e:
        result_print('List Classes', False, str(e))
