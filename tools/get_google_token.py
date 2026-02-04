import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']

def main():
    """Outputs the GOOGLE_TOKEN_JSON content from a credentials.json file."""
    print("=== Google Drive Token Generator ===")
    
    cred_file = 'credentials.json'
    if not os.path.exists(cred_file):
        print(f"Error: {cred_file} not found!")
        print("Please download your OAuth 2.0 Client ID JSON from Google Cloud Console")
        print("and rename it to 'credentials.json' in this folder.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(cred_file, SCOPES)
    creds = flow.run_local_server(port=0)
    
    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    
    print("\n" + "="*50)
    print("BERHASIL! Copy teks di bawah ini ke GOOGLE_TOKEN_JSON di file .env Anda:")
    print("="*50 + "\n")
    print(json.dumps(token_data))
    print("\n" + "="*50)

if __name__ == '__main__':
    main()
