"""
Google Drive Integration Service
Uses OAuth2 with credentials from environment variables
Fallback to Service Account if OAuth fails
"""
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']

class GoogleDriveService:
    def __init__(self):
        self.folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
        self.token_json = os.getenv("GOOGLE_TOKEN_JSON", "")
        self.credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
        self.service_account_json = os.getenv("SERVICE_ACCOUNT_JSON", "")
        self.service = None
        self.enabled = False
        self.folders_cache = {}
        self.auth_method = None  # Track which auth method was used
        
        print("[INFO] Initializing Google Drive Service...")
        print(f"  [DEBUG] GOOGLE_DRIVE_FOLDER_ID: {self.folder_id[:20] + '...' if self.folder_id else 'NOT SET'}")
        print(f"  [DEBUG] GOOGLE_TOKEN_JSON length: {len(self.token_json)} chars")
        print(f"  [DEBUG] SERVICE_ACCOUNT_JSON length: {len(self.service_account_json)} chars")
        print(f"  [DEBUG] GOOGLE_CREDENTIALS_JSON length: {len(self.credentials_json)} chars")
        
        if not self.folder_id:
            print("[ERROR] GOOGLE_DRIVE_FOLDER_ID not set - cannot initialize Drive service")
            return
        
        # Try to initialize the service
        try:
            self.service = self._get_drive_service()
            self.enabled = bool(self.service)
            if self.enabled:
                print(f"[OK] Google Drive service initialized via {self.auth_method}!")
        except Exception as e:
            print(f"[ERROR] Google Drive initialization failed: {e}")
            import traceback
            traceback.print_exc()
            self.enabled = False
    
    def _get_drive_service(self):
        """Get Google Drive service - try OAuth first, then Service Account fallback"""
        
        # Method 1: Try OAuth2 token
        if self.token_json:
            try:
                print("[INFO] Attempting OAuth2 token authentication...")
            # Parse token JSON from environment variable
                token_info = json.loads(self.token_json)
                
                # Create credentials object
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
                
                # Check if token needs refresh
                if creds and creds.expired and creds.refresh_token:
                    print("[INFO] Refreshing expired OAuth token...")
                    try:
                        creds.refresh(Request())
                        print("[OK] Token refreshed successfully")
                        # NOTE: We can't save the new token back to env/secrets from here
                        # It will only last for this session or until expiry
                    except Exception as refresh_err:
                        print(f"[WARN] Failed to refresh token: {refresh_err}")
                        # If refresh fails, we might still try to use it or fail to fallback
                        raise refresh_err

                print("[OK] OAuth credentials loaded from env")
                self.auth_method = "OAuth2" if not creds.expired else "OAuth2 (refreshed)"
                return build('drive', 'v3', credentials=creds)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse GOOGLE_TOKEN_JSON: {e}")
            except Exception as e:
                print(f"[WARN] OAuth2 authentication failed: {e}")
        else:
            print("[INFO] GOOGLE_TOKEN_JSON not set, skipping OAuth2")
        
        # Method 2: Fallback to Service Account
        if self.service_account_json:
            try:
                print("[INFO] Attempting Service Account authentication...")
                from google.oauth2 import service_account
                sa_info = json.loads(self.service_account_json)
                print(f"  [DEBUG] Service Account email: {sa_info.get('client_email', 'N/A')}")
                creds = service_account.Credentials.from_service_account_info(
                    sa_info, scopes=SCOPES
                )
                print("[OK] Service Account credentials loaded")
                self.auth_method = "Service Account"
                return build('drive', 'v3', credentials=creds)
            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse SERVICE_ACCOUNT_JSON: {e}")
            except Exception as e:
                print(f"[ERROR] Service Account authentication failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("[INFO] SERVICE_ACCOUNT_JSON not set, skipping Service Account")
        
        # Neither method worked
        print("[ERROR] All authentication methods failed!")
        return None
    
    def find_or_create_folder(self, folder_name: str, parent_id: str = None, prefix_search: bool = False) -> str:
        """Find existing folder or create new one by name. 
           If prefix_search=True, matches folder starting with folder_name (and space).
           e.g. searching for "2.1" finds "2.1 HSE Committee Meeting"
        """
        if not self.enabled or not self.service:
            print("[WARN] Drive not enabled")
            return None
        
        try:
            parent_id = parent_id or self.folder_id
            
            # Check cache (Exact match only for cache safety)
            cache_key = f"{parent_id}:{folder_name}"
            if not prefix_search and cache_key in self.folders_cache:
                print(f"[CACHE] Using cached folder: {folder_name}")
                return self.folders_cache[cache_key]
            
            # Search Query
            if prefix_search:
                # Find folders starting with "Name " (with space) or exactly "Name" to avoid 2.1 matching 2.10
                query = f"(name = '{folder_name}' or name contains '{folder_name} ') and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            else:
                query = f"name='{folder_name}' and '{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                
            results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            files = results.get('files', [])
            
            if files:
                # If multiple matches, pick the best one (prefer exact match or shortest/first)
                # Sort: exact match first, then others
                files.sort(key=lambda x: (x['name'] != folder_name, x['name']))
                folder_id = files[0]['id']
                
                # Update cache only if exact match
                if files[0]['name'] == folder_name:
                    self.folders_cache[cache_key] = folder_id
                
                print(f"[FOUND] Existing folder: {files[0]['name']}")
                return folder_id
            
            # Create new folder (Only if not searching with prefix)
            # If we are in prefix mode and didn't find it, we usually want to CREATE the base name
            # e.g. if "2.1 HSE" exists, we found it. If not, create "2.1" (or whatever was passed)
            
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            file = self.service.files().create(body=file_metadata, fields='id').execute()
            folder_id = file.get('id')
            self.folders_cache[cache_key] = folder_id
            print(f"[CREATED] New folder: {folder_name}")
            return folder_id
            
        except Exception as e:
            print(f"[ERROR] Error finding/creating folder: {e}")
            return None

    def create_nested_task_folder(self, project_name: str, task_code: str, task_title: str = "") -> str:
        """Create nested folder structure based on task code hierarchy."""
        if not self.enabled or not self.service:
            print("[WARN] Drive not enabled for nested folder creation")
            return None
        
        if not task_code:
            print("[WARN] No task code provided, falling back to project folder")
            return self.find_or_create_folder(project_name)
        
        try:
            # 1. Create/find project folder
            project_folder_id = self.find_or_create_folder(project_name)
            if not project_folder_id:
                print("[ERROR] Could not create project folder")
                return None
            
            # 2. Parse task code (e.g., "3.1.1" → ["3", "1", "1"])
            parts = task_code.split('.')
            if not parts:
                return project_folder_id
            
            # 3. Create Element folder (first part, e.g., "Element 1")
            element_folder_name = f"Element {parts[0]}"
            current_parent_id = self.find_or_create_folder(element_folder_name, project_folder_id)
            if not current_parent_id:
                print(f"[ERROR] Could not create element folder: {element_folder_name}")
                return project_folder_id
            
            print(f"[NESTED] Created/found: {project_name}/{element_folder_name}")
            
            # 4. Create intermediate folders for remaining parts
            for i in range(1, len(parts)):
                folder_code = '.'.join(parts[:i+1])  # "3.1", "3.1.1"
                
                # Check if this is the FINAL folder
                is_last_folder = (folder_code == task_code)
                
                if is_last_folder:
                    # Final folder: We always create/find specific name "[Code] [Title]" if title exists
                    if task_title:
                        safe_title = "".join(x for x in task_title if (x.isalnum() or x in "._- "))
                        target_name = f"{folder_code} {safe_title}"
                    else:
                        target_name = folder_code
                    
                    # We use standard find_or_create because we know the exact full name we want
                    current_parent_id = self.find_or_create_folder(target_name, current_parent_id)
                    
                else:
                    # Intermediate folder (e.g. "3.1"): Use PREFIX SEARCH
                    # Try to find "3.1 Title" OR just "3.1"
                    current_parent_id = self.find_or_create_folder(folder_code, current_parent_id, prefix_search=True)
                
                if not current_parent_id:
                    print(f"[ERROR] Could not create folder: {folder_code}")
                    return None
                print(f"[NESTED] Created/found: .../{folder_code}")
            
            return current_parent_id
            
        except Exception as e:
            print(f"[ERROR] Error creating nested folder structure: {e}")
            return None

    async def upload_file_to_drive(self, file_data: bytes, filename: str, project_name: str, task_code: str = None, task_title: str = "") -> dict:
        """Upload file to Google Drive folder with nested task folder structure.
        
        Returns: dict with 'success', 'file_id', and 'folder_path' or None on failure
        """
        if not self.enabled or not self.service:
            print("[WARN] Google Drive not enabled")
            return {"success": False, "file_id": None, "folder_path": None}
        
        try:
            # Use nested folder structure based on task code
            if task_code:
                target_folder_id = self.create_nested_task_folder(project_name, task_code, task_title)
                
                # Format folder path for debug/return info
                safe_title = "".join(x for x in task_title if (x.isalnum() or x in "._- ")) if task_title else ""
                folder_suffix = f" {safe_title}" if safe_title else ""
                folder_path = f"{project_name}/Element {task_code.split('.')[0]}/{task_code}{folder_suffix}"
            else:
                # Fallback to project folder only
                target_folder_id = self.find_or_create_folder(project_name)
                folder_path = project_name
            
            if not target_folder_id:
                print("[ERROR] Could not get target folder ID")
                return {"success": False, "file_id": None, "folder_path": None}

            # Upload File to that folder
            file_metadata = {
                'name': filename,
                'parents': [target_folder_id]
            }
            
            media = MediaInMemoryUpload(file_data, resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            print(f"[OK] File uploaded to Google Drive: {folder_path}/{filename} (ID: {file_id})")
            return {"success": True, "file_id": file_id, "folder_path": folder_path}
            
        except Exception as e:
            print(f"[ERROR] Error uploading to Google Drive: {e}")
            return {"success": False, "file_id": None, "folder_path": None}

    def upload_file(self, filename: str, file_content: bytes, folder_name: str = None) -> str:
        """Upload file to Google Drive and return file ID
        
        Args:
            filename: Name of the file
            file_content: Binary content of the file
            folder_name: Optional subfolder name (creates under root CSMS folder)
        
        Returns:
            File ID if successful, None if failed
        """
        if not self.enabled or not self.service:
            print("[WARN] Google Drive not enabled, can't upload file")
            return None
        
        try:
            # Determine parent folder
            parent_id = self.folder_id
            if folder_name:
                # Create/find subfolder
                parent_id = self.find_or_create_folder(folder_name) or self.folder_id
            
            # Upload file
            file_metadata = {
                'name': filename,
                'parents': [parent_id]
            }
            
            media = MediaInMemoryUpload(file_content, resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            print(f"[OK] File uploaded: {filename} -> {file_id}")
            return file_id
            
        except Exception as e:
            print(f"[ERROR] Error uploading file: {e}")
            return None

    def find_file_in_folder(self, filename: str, project_name: str) -> str:
        """Find a file by name in a project folder"""
        if not self.enabled or not self.service:
            return None
        
        try:
            # First find project folder
            project_folder_id = self.find_or_create_folder(project_name)
            if not project_folder_id:
                return None
            
            # Search for file
            query = f"name='{filename}' and '{project_folder_id}' in parents and trashed=false"
            results = self.service.files().list(q=query, spaces='drive', fields='files(id, name, mimeType)').execute()
            files = results.get('files', [])
            
            if files:
                return files[0]['id']
            return None
            
        except Exception as e:
            print(f"[ERROR] Error finding file: {e}")
            return None
    
    def _find_file_recursive(self, filename: str, folder_id: str, depth: int = 0) -> str:
        """Recursively search for a file in folder and all subfolders"""
        if depth > 5:  # Limit recursion depth
            return None
        
        try:
            # First search in current folder
            query = f"name='{filename}' and '{folder_id}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'"
            results = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
            files = results.get('files', [])
            
            if files:
                print(f"[FOUND] File '{filename}' at depth {depth}")
                return files[0]['id']
            
            # Get all subfolders
            folder_query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            folder_results = self.service.files().list(q=folder_query, spaces='drive', fields='files(id, name)').execute()
            subfolders = folder_results.get('files', [])
            
            # Search in each subfolder
            for subfolder in subfolders:
                file_id = self._find_file_recursive(filename, subfolder['id'], depth + 1)
                if file_id:
                    return file_id
            
            return None
            
        except Exception as e:
            print(f"[ERROR] Recursive search error: {e}")
            return None
    
    def download_file(self, file_id: str) -> bytes:
        """Download a file from Google Drive by ID"""
        if not self.enabled or not self.service:
            return None
        
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            request = self.service.files().get_media(fileId=file_id)
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            buffer.seek(0)
            return buffer.read()
            
        except Exception as e:
            print(f"[ERROR] Error downloading file: {e}")
            return None
    
    def get_files_in_project(self, project_name: str) -> list:
        """Get all files in a project folder"""
        if not self.enabled or not self.service:
            return []
        
        try:
            project_folder_id = self.find_or_create_folder(project_name)
            if not project_folder_id:
                return []
            
            query = f"'{project_folder_id}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'"
            results = self.service.files().list(q=query, spaces='drive', fields='files(id, name, mimeType)').execute()
            return results.get('files', [])
            
        except Exception as e:
            print(f"[ERROR] Error listing files: {e}")
            return []
    
    def export_file_as_pdf(self, file_id: str) -> bytes:
        """Export a Google Workspace file (Docs, Sheets, Slides) as PDF"""
        if not self.enabled or not self.service:
            return None
        
        try:
            request = self.service.files().export_media(
                fileId=file_id,
                mimeType='application/pdf'
            )
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            buffer.seek(0)
            return buffer.read()
            
        except Exception as e:
            print(f"[ERROR] Error exporting file as PDF: {e}")
            return None
    
    def get_file_info(self, file_id: str) -> dict:
        """Get file metadata including mimeType"""
        if not self.enabled or not self.service:
            return None
        
        try:
            file = self.service.files().get(fileId=file_id, fields='id, name, mimeType').execute()
            return file
        except Exception as e:
            print(f"[ERROR] Error getting file info: {e}")
            return None

    def convert_office_to_pdf(self, file_id: str, filename: str) -> bytes:
        """Convert an uploaded Office file to PDF using Google Drive conversion
        
        This works by:
        1. Making a copy of the file with Google's conversion (imports to Google format)
        2. Exporting that copy as PDF
        3. Deleting the temporary copy
        """
        if not self.enabled or not self.service:
            return None
        
        file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        # Map Office extensions to Google import types
        google_mime_types = {
            'docx': 'application/vnd.google-apps.document',
            'doc': 'application/vnd.google-apps.document',
            'xlsx': 'application/vnd.google-apps.spreadsheet',
            'xls': 'application/vnd.google-apps.spreadsheet',
            'pptx': 'application/vnd.google-apps.presentation',
            'ppt': 'application/vnd.google-apps.presentation',
        }
        
        target_mime = google_mime_types.get(file_ext)
        if not target_mime:
            print(f"[WARN] Unsupported file type for conversion: {file_ext}")
            return None
        
        temp_file_id = None
        try:
            # Step 1: Copy the file and convert to Google format
            copy_metadata = {
                'name': f'_temp_convert_{filename}',
                'mimeType': target_mime
            }
            copied_file = self.service.files().copy(
                fileId=file_id,
                body=copy_metadata
            ).execute()
            temp_file_id = copied_file.get('id')
            print(f"[INFO] Created temp Google file: {temp_file_id}")
            
            # Step 2: Export as PDF
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            request = self.service.files().export_media(
                fileId=temp_file_id,
                mimeType='application/pdf'
            )
            
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            buffer.seek(0)
            pdf_bytes = buffer.read()
            print(f"[OK] Converted {filename} to PDF ({len(pdf_bytes)} bytes)")
            
            return pdf_bytes
            
        except Exception as e:
            print(f"[ERROR] Error converting Office to PDF: {e}")
            return None
            
        finally:
            # Step 3: Delete the temporary file
            if temp_file_id:
                try:
                    self.service.files().delete(fileId=temp_file_id).execute()
                    print(f"[INFO] Deleted temp file: {temp_file_id}")
                except Exception as e:
                    print(f"[WARN] Could not delete temp file: {e}")
