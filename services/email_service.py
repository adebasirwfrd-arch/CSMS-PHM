import os
import requests
import json
from datetime import datetime
from typing import List, Dict, Optional

class EmailService:
    def __init__(self):
        self.api_key = os.getenv('BREVO_API_KEY')
        self.sender_email = os.getenv('BREVO_SENDER_EMAIL', 'ade.basirwfrd@gmail.com')
        self.sender_name = os.getenv('BREVO_SENDER_NAME', 'CSMS PHM')
        self.api_url = "https://api.brevo.com/v3/smtp/email"
        
        if not self.api_key:
            print("[WARN] BREVO_API_KEY not set in environment variables")

    def _send_email(self, to_emails: List[str], subject: str, html_content: str, cc_emails: List[str] = None) -> bool:
        """Base method to send email using Brevo API"""
        if not self.api_key:
            print("[EMAIL ERROR] Cannot send email: API key missing")
            return False
            
        if not to_emails:
            print("[EMAIL ERROR] No recipients provided")
            return False
            
        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json"
        }
        
        payload = {
            "sender": {"name": self.sender_name, "email": self.sender_email},
            "to": [{"email": email} for email in to_emails],
            "subject": subject,
            "htmlContent": html_content
        }
        
        if cc_emails:
            payload["cc"] = [{"email": email} for email in cc_emails]
            
        try:
            response = requests.post(self.api_url, json=payload, headers=headers)
            if response.status_code in [200, 201, 202]:
                print(f"[EMAIL] Successfully sent email: '{subject}' to {to_emails}")
                return True
            else:
                print(f"[EMAIL ERROR] Failed to send: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"[EMAIL ERROR] Exception sending email: {e}")
            return False

    def send_schedule_notification(self, schedule: Dict) -> bool:
        """Send email notification about a new or updated schedule"""
        recipient = schedule.get('assigned_to_email')
        if not recipient:
            print("[EMAIL WARN] No assigned_to_email for schedule")
            return False

        # Determine schedule type and format accordingly
        schedule_type = schedule.get('schedule_type', 'mwt').lower()
        
        # Map schedule type to display name and get the relevant date
        type_config = {
            'mwt': {'name': 'MWT Plan', 'date_field': 'mwt_plan_date', 'color': '#3498db'},
            'hse_committee': {'name': 'HSE Committee Meeting', 'date_field': 'hse_meeting_date', 'color': '#9b59b6'},
            'csms_pb': {'name': 'CSMS PB Audit', 'date_field': 'csms_pb_date', 'color': '#27ae60'},
            'hse_plan': {'name': 'HSE Plan', 'date_field': 'hse_plan_date', 'color': '#e67e22'},
            'spr': {'name': 'SPR Review', 'date_field': 'spr_date', 'color': '#1abc9c'},
            'hazid_hazop': {'name': 'HAZID/HAZOP', 'date_field': 'hazid_hazop_date', 'color': '#e74c3c'},
        }
        
        config = type_config.get(schedule_type, type_config['mwt'])
        schedule_name = config['name']
        schedule_date = schedule.get(config['date_field']) or schedule.get('mwt_plan_date') or 'TBD'
        schedule_color = config['color']
        
        subject = f"Schedule Reminder: {schedule_name} - {schedule.get('project_name', 'Unknown Project')}"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: {schedule_color}; color: white; padding: 20px; border-radius: 8px;">
                <h2 style="margin: 0;">{schedule_name} Reminder</h2>
            </div>
            <div style="padding: 20px; background: #f5f5f5; border-radius: 8px; margin-top: 10px;">
                <p>Dear <strong>{schedule.get('pic_name', 'User')}</strong>,</p>
                <p>This is a reminder for your upcoming <strong>{schedule_name}</strong> schedule:</p>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Project</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{schedule.get('project_name', '-')}</td>
                    </tr>
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Well</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{schedule.get('well_name', '-')}</td>
                    </tr>
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Schedule Type</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd; color: {schedule_color}; font-weight: bold;">{schedule_name}</td>
                    </tr>
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Date</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd; color: {schedule_color}; font-weight: bold;">{schedule_date}</td>
                    </tr>
                </table>
                <p style="margin-top: 20px;">Please mark this date in your calendar and prepare accordingly.</p>
                <p>Best regards,<br><strong>CSMS Project Management System</strong><br>PHM</p>
            </div>
        </body>
        </html>
        """
        
        return self._send_email([recipient], subject, body_html)

    def send_project_rig_down_alert(self, project: Dict, days_until: int, total_tasks: int, is_new_project: bool = True) -> bool:
        """Send alert for imminent rig down"""
        pic_email_str = project.get('pic_email') or project.get('assigned_to_email') or ''
        if not pic_email_str:
            print(f"[EMAIL WARN] No PIC email for project {project.get('name')}")
            return False
            
        recipients = [e.strip() for e in pic_email_str.split(',') if e.strip()]
        
        cc_email_str = project.get('pic_manager_email', '')
        cc_emails = [e.strip() for e in cc_email_str.split(',') if e.strip()] if cc_email_str else []
        
        rig_down_str = project.get('rig_down_date') or project.get('rig_down') or 'Unknown'
        
        if is_new_project:
            title = "[ALERT] New Project - Rig Down Alert"
            subject = f"[ALERT] New Project: {project['name']} - Rig Down in {days_until} Day(s)"
            intro = f"A new project has been created with <strong style='color:#E50914;'>rig down in {days_until} day(s)</strong>."
        else:
            # For reminders
            title = "[REMINDER] Project Completion Alert"
            subject = f"[REMINDER] Project: {project['name']} - Rig Down in {days_until} Day(s)"
            intro = f"This is a reminder that the repository has <strong style='color:#E50914;'>rig down in {days_until} day(s)</strong>."

        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: #E50914; color: white; padding: 20px; border-radius: 8px;">
                <h2 style="margin: 0;">{title}</h2>
            </div>
            <div style="padding: 20px; background: #f5f5f5; border-radius: 8px; margin-top: 10px;">
                <p>Dear Team,</p>
                <p>{intro}</p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Project</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{project['name']}</td>
                    </tr>
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Well</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{project.get('well_name') or project.get('well', 'N/A')}</td>
                    </tr>
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Rig Down Date</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd; color: #E50914; font-weight: bold;">{rig_down_str}</td>
                    </tr>
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Total Tasks</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{total_tasks}</td>
                    </tr>
                </table>
                <p style="color: #E50914; font-weight: bold;">Please prioritize tasks before rig down.</p>
                <p>Best regards,<br><strong>CSMS Project Management System</strong><br>PHM</p>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(recipients, subject, body_html, cc_emails)

    def send_completion_reminder(self, project: Dict, days_until: int, completion_pct: float, completed_tasks: int, total_tasks: int) -> bool:
        """Send specific reminder about project completion status"""
        pic_email_str = project.get('pic_email') or project.get('assigned_to_email') or ''
        recipients = [e.strip() for e in pic_email_str.split(',') if e.strip()]
        
        cc_email_str = project.get('pic_manager_email', '')
        cc_emails = [e.strip() for e in cc_email_str.split(',') if e.strip()] if cc_email_str else []
        
        if not recipients:
            return False
            
        rig_down_str = project.get('rig_down_date') or project.get('rig_down') or 'Unknown'
        
        subject = f"[REMINDER] Project: {project['name']} - {completion_pct:.0f}% Complete"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: #E50914; color: white; padding: 20px; border-radius: 8px;">
                <h2 style="margin: 0;">[REMINDER] Project Completion Alert</h2>
            </div>
            <div style="padding: 20px; background: #f5f5f5; border-radius: 8px; margin-top: 10px;">
                <p>Dear Team,</p>
                <p>This is a reminder that the following project has <strong style="color:#E50914;">rig down in {days_until} day(s)</strong> but is only <strong>{completion_pct:.0f}% complete</strong>.</p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Project</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{project['name']}</td>
                    </tr>
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Rig Down Date</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd; color: #E50914; font-weight: bold;">{rig_down_str}</td>
                    </tr>
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Completion</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{completed_tasks}/{total_tasks} tasks ({completion_pct:.0f}%)</td>
                    </tr>
                    <tr style="background: #fff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Remaining Tasks</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd; color: #E50914;">{total_tasks - completed_tasks} tasks to complete</td>
                    </tr>
                </table>
                <p style="color: #E50914; font-weight: bold;">Please prioritize completing the remaining tasks before rig down.</p>
                <p>Best regards,<br><strong>CSMS Project Management System</strong><br>PHM</p>
            </div>
        </body>
        </html>
        """
        
        return self._send_email(recipients, subject, body_html, cc_emails)

# Global Instance
email_service = EmailService()
