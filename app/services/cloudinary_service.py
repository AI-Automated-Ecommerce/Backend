import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import uuid

load_dotenv()

# Configure Cloudinary
cloudinary.config( 
  cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'), 
  api_key = os.getenv('CLOUDINARY_API_KEY'), 
  api_secret = os.getenv('CLOUDINARY_API_SECRET'),
  secure = True
)

def upload_to_cloudinary(file_content, filename: str) -> str:
    """
    Uploads a file to Cloudinary and returns the secure URL.
    """
    try:
        # Generate a unique public_id
        unique_id = str(uuid.uuid4())[:8]
        public_id = f"{os.path.splitext(filename)[0]}_{unique_id}"
        
        # Upload the file
        # resource_type="auto" allows uploading images, videos, etc.
        response = cloudinary.uploader.upload(
            file_content, 
            public_id=public_id,
            resource_type="auto"
        )
        
        return response['secure_url']
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        raise e
