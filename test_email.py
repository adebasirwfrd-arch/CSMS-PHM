
import os
from dotenv import load_dotenv

# Load env BEFORE importing services that might initialize immediately
load_dotenv()

from services.email_service import EmailService

def test_brevo():
    print("Testing Brevo API...")
    email_service = EmailService()
    
    # Send to the sender itself for testing
    recipient = "ade.basirwfrd@gmail.com" 
    subject = "CSMS Backend - Brevo Test"
    content = "<h1>It Works!</h1><p>This is a test email from the CSMS Backend commissioning.</p>"
    
    print(f"Sending test email to {recipient}...")
    success = email_service._send_email([recipient], subject, content)
    
    if success:
        print("SUCCESS: Email sent successfully via Brevo!")
    else:
        print("FAILED: Could not send email.")

if __name__ == "__main__":
    test_brevo()
