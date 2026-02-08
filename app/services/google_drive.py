import os
import io
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    """Create and return Google Drive API service."""
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')

    # Strip quotes if they exist (common in Windows .env)
    if client_id:
        client_id = client_id.strip('"').strip("'")
    if client_secret:
        client_secret = client_secret.strip('"').strip("'")
    if refresh_token:
        refresh_token = refresh_token.strip('"').strip("'")

    if not refresh_token:
        return None
    
    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(file_content: bytes, filename: str, mimetype: str):
    """Upload a file to Google Drive and return its public URL."""
    service = get_drive_service()
    if not service:
        raise Exception(
            "Google Drive Authentication missing. Please ensure GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN are in your .env"
        )

    # Get folder ID from environment
    target_folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    if target_folder_id:
        target_folder_id = target_folder_id.strip('"').strip("'")

    # Prepare file metadata
    file_metadata = {'name': filename}
    if target_folder_id:
        file_metadata['parents'] = [target_folder_id]

    # Upload file
    fh = io.BytesIO(file_content)
    media = MediaIoBaseUpload(fh, mimetype=mimetype, resumable=True)
    
    try:
        # Create the file
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        file_id = file.get('id')
        
        # Set public permissions
        try:
            service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'},
                supportsAllDrives=True,
                fields='id'
            ).execute()
        except Exception:
            # If permission setting fails, file is still uploaded but may be private
            pass

        return f"https://lh3.googleusercontent.com/d/{file_id}"
        
    except Exception as e:
        raise Exception(f"Google Drive upload failed: {str(e)}")
