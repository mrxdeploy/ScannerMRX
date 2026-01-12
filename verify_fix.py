import urllib.request
import urllib.parse
import json

try:
    # 1. Create empty folder
    print("Creating TEST_EMPTY...")
    data = urllib.parse.urlencode({"name": "TEST_EMPTY"}).encode()
    req = urllib.request.Request("http://localhost:5000/dataset/create", data=data)
    with urllib.request.urlopen(req) as response:
        print(response.read().decode())
    
    # 2. List classes
    print("Listing classes...")
    with urllib.request.urlopen("http://localhost:5000/dataset/classes") as response:
        data = json.loads(response.read().decode())
        classes = data["classes"]
        found = False
        for c in classes:
            if c["name"] == "TEST_EMPTY":
                print(f"Found class: {c}")
                found = True
                if c["image_count"] == 0:
                    print("Confirmed image_count is 0")
                else:
                    print(f"Unexpected image_count: {c['image_count']}")
        
        if not found:
            print("TEST_EMPTY not found in classes list!")
            exit(1)

    print("Verification successful!")

except Exception as e:
    print(f"Error: {e}")
    exit(1)
