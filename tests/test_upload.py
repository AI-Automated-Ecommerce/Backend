import requests
import os

# You need to run the backend first
BACKEND_URL = "http://localhost:8000"

def test_upload_image():
    print("Testing Image Upload...")
    
    # Create a dummy image file
    dummy_filename = "test_image.txt"
    with open(dummy_filename, "wb") as f:
        f.write(b"fake image content")
        
    try:
        files = {'file': (dummy_filename, open(dummy_filename, 'rb'), "text/plain")}
        response = requests.post(f"{BACKEND_URL}/admin/upload", files=files)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Upload Successful! URL: {data['imageUrl']}")
            return data['imageUrl']
        else:
            print(f"❌ Upload Failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None
    finally:
        if os.path.exists(dummy_filename):
            os.remove(dummy_filename)

if __name__ == "__main__":
    test_upload_image()
