

from dotenv import load_dotenv
load_dotenv()

import sys
sys.setrecursionlimit(2000)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil
import json
import io
import requests  # For Brevo API
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.google_drive import GoogleDriveService
from config import STANDARD_TASKS
from database import (
    Database, TASKS_FILE, PROJECTS_FILE, SCHEDULES_FILE, COMMENTS_FILE, CSMS_PB_FILE, RELATED_DOCS_FILE,
    get_schedules, save_schedules, save_schedule, delete_schedule,
    get_comments, save_comments, save_comment, update_comment, delete_comment,
    get_csms_pb_records, save_csms_pb_records, save_csms_pb, update_csms_pb, delete_csms_pb,
    get_related_docs, save_related_docs, save_related_doc, delete_related_doc
)
# Import Supabase service for direct operations
try:
    from services.supabase_service import supabase_service, SUPABASE_AVAILABLE
except ImportError:
    supabase_service = None

try:
    from services.supabase_service import supabase_service, SUPABASE_AVAILABLE
except ImportError:
    supabase_service = None
    SUPABASE_AVAILABLE = False

from routers.reports import router as reports_router


app = FastAPI()

print("[INFO] Starting CSMS Backend with Google Drive Fix v2 (Force Update)")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database()
drive_service = GoogleDriveService()

# Mount static files for assets (logo, etc.)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include Routers
app.include_router(reports_router)

# NOTE: All database functions (get_schedules, save_schedules, etc.) are now imported from database.py
# which handles Supabase cloud storage with JSON file fallback

# Models
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    well_name: Optional[str] = None
    kontrak_no: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    rig_down_date: Optional[str] = None
    rig_down: Optional[str] = None  # Alias for rig_down_date
    pic_email: Optional[str] = None
    pic_manager_email: Optional[str] = None  # CC email for reminders
    status: str = "Ongoing"

class TaskCreate(BaseModel):
    title: str
    project_id: str
    code: Optional[str] = None
    category: Optional[str] = None
    status: str = "Upcoming"
    description: Optional[str] = ""

class ScheduleCreate(BaseModel):
    project_id: str
    project_name: str
    well_name: str
    schedule_type: str = "mwt"  # mwt, hse, or csms
    mwt_plan_date: Optional[str] = None
    hse_meeting_date: Optional[str] = None
    csms_pb_date: Optional[str] = None
    pic_name: str
    assigned_to_email: str

class CSMSPBCreate(BaseModel):
    project_id: str
    well_name: Optional[str] = None
    pb_date: str
    pic_name: str
    pic_whatsapp: Optional[str] = None
    score: float  # 0-100

class RelatedDocCreate(BaseModel):
    project_id: str
    well_name: Optional[str] = None
    doc_name: str

class CommentCreate(BaseModel):
    author_name: str = "User"
    content: str
    attachment_filename: Optional[str] = None
    attachment_data: Optional[str] = None  # Base64 data URL for images

# NOTE: All data functions (get_csms_pb_records, get_related_docs, etc.) are imported from database.py


# Email Service Import
from services.email_service import email_service

# NOTE: All data functions (get_csms_pb_records, get_related_docs, etc.) are imported from database.py


# Routes

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serve the frontend app"""
    static_path = Path(__file__).parent / "static" / "index.html"
    if static_path.exists():
        return static_path.read_text(encoding='utf-8')
    return """
    <html>
        <body style="background:#141414;color:white;font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;">
            <div style="text-align:center;">
                <h1 style="color:#C41E3A;">CSMS Backend</h1>
                <p>API is running. Upload index.html to /static folder.</p>
            </div>
        </body>
    </html>
    """

@app.get("/api/status")
def api_status():
    return {"status": "ok", "service": "CSMS Backend"}

@app.get("/api/debug/supabase")
def debug_supabase():
    """Debug endpoint to check Supabase connection status"""
    import os
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_KEY", "")
    
    # Import to check if available
    try:
        from database import SUPABASE_ENABLED
        from services.supabase_service import supabase_service
        service_enabled = supabase_service.enabled if supabase_service else False
    except ImportError:
        SUPABASE_ENABLED = False
        service_enabled = False
    
    return {
        "supabase_url_set": bool(supabase_url),
        "supabase_url_preview": supabase_url[:30] + "..." if supabase_url else "NOT SET",
        "supabase_key_set": bool(supabase_key),
        "database_enabled": SUPABASE_ENABLED,
        "service_enabled": service_enabled,
        "message": "Check HF Secrets if supabase_url_set or supabase_key_set is False"
    }

@app.post("/api/force-sync")
def force_sync_from_supabase():
    """Force restore all data from Supabase to local files - USE WITH CAUTION!"""
    if not supabase_service or not supabase_service.enabled:
        raise HTTPException(status_code=400, detail="Supabase not enabled")
    
    try:
        from database import PROJECTS_FILE, TASKS_FILE
        import json
        
        results = {"projects": 0, "tasks": 0, "message": ""}
        
        # Force sync projects
        cloud_projects = supabase_service.get_projects()
        if cloud_projects:
            with open(PROJECTS_FILE, 'w') as f:
                json.dump(cloud_projects, f, indent=2)
            results["projects"] = len(cloud_projects)
            print(f"[FORCE SYNC] Restored {len(cloud_projects)} projects from Supabase")
        
        # Force sync tasks
        cloud_tasks = supabase_service.get_tasks()
        if cloud_tasks:
            with open(TASKS_FILE, 'w') as f:
                json.dump(cloud_tasks, f, indent=2)
            results["tasks"] = len(cloud_tasks)
            print(f"[FORCE SYNC] Restored {len(cloud_tasks)} tasks from Supabase")
        
        results["message"] = f"Restored {results['projects']} projects and {results['tasks']} tasks from Supabase"
        return results
        
    except Exception as e:
        print(f"[FORCE SYNC ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send-reminders")
def send_reminders(background_tasks: BackgroundTasks):
    """Send email reminders for projects with rig down within 2 days and completion < 80% - Uses Brevo API"""
    import requests
    from datetime import datetime, timedelta
    
    projects = db.get_projects()
    tasks = db.get_tasks()
    sent_count = 0
    reminders_info = []
    
    # Get Brevo API key
    brevo_api_key = os.getenv('BREVO_API_KEY')
    
    if not brevo_api_key:
        print("[EMAIL] BREVO_API_KEY not found in environment")
        return {"message": "Email not configured (Brevo API key missing)", "count": 0}
    
    today = datetime.now().date()
    
    print(f"[REMINDER] Checking {len(projects)} projects, today is {today}")
    
    for project in projects:
        try:
            # Check rig down date (rig_down_date, estimasi_rig_down, or rig_down from frontend)
            rig_down_str = project.get('rig_down_date') or project.get('rig_down') or project.get('estimasi_rig_down', '')
            if not rig_down_str:
                print(f"[REMINDER] Project {project.get('name', 'Unknown')}: No rig down date, skipping")
                continue
            
            try:
                rig_down_date = datetime.strptime(rig_down_str, '%Y-%m-%d').date()
            except:
                print(f"[REMINDER] Project {project.get('name', 'Unknown')}: Invalid date format '{rig_down_str}'")
                continue
            
            # Calculate days until rig down
            days_until_rig_down = (rig_down_date - today).days
            print(f"[REMINDER] Project {project.get('name', 'Unknown')}: {days_until_rig_down} days until rig down ({rig_down_str})")
            
            # Check if rig down is within 2 days (0, 1, or 2 days from today)
            if days_until_rig_down < 0 or days_until_rig_down > 2:
                print(f"[REMINDER] Project {project.get('name', 'Unknown')}: Not within 2 days, skipping")
                continue
            
            # Calculate task completion for this project
            project_tasks = [t for t in tasks if t.get('project_id') == project.get('id')]
            if not project_tasks:
                print(f"[REMINDER] Project {project.get('name', 'Unknown')}: No tasks, skipping")
                continue
                
            completed = len([t for t in project_tasks if t.get('status') == 'Completed'])
            total = len(project_tasks)
            completion_pct = (completed / total * 100) if total > 0 else 0
            
            print(f"[REMINDER] Project {project.get('name', 'Unknown')}: {completion_pct:.0f}% complete ({completed}/{total})")
            
            # Only send reminder if completion is below 80%
            if completion_pct >= 80:
                print(f"[REMINDER] Project {project.get('name', 'Unknown')}: Completion >= 80%, skipping")
                continue
            
            # Get PIC email(s) from project - support multiple emails (comma separated)
        pic_email_str = project.get('pic_email') or project.get('assigned_to_email') or ''
        if not pic_email_str:
            pic_email_str = os.getenv('DEFAULT_REMINDER_EMAIL', 'csms-notify@phm.co.id')
            
            # Split by comma and clean up
            pic_emails = [email.strip() for email in pic_email_str.split(',') if email.strip()]
            
            # Get PIC Manager email for CC
            pic_manager_email_str = project.get('pic_manager_email') or ''
            cc_emails = [email.strip() for email in pic_manager_email_str.split(',') if email.strip()]
            
            if not pic_emails:
                print(f"[REMINDER] Project {project.get('name', 'Unknown')}: No valid emails, skipping")
                continue
            
            print(f"[REMINDER] Sending via Brevo API to: {pic_emails}, CC: {cc_emails}")
            
            # Send reminder email using EmailService
            try:
                success = email_service.send_completion_reminder(project, days_until_rig_down, completion_pct, completed, total)
                
                if success:
                    sent_count += 1
                    reminders_info.append(f"{project['name']}: {completion_pct:.0f}% complete, sent to {len(pic_emails)} recipient(s)")
                else:
                    reminders_info.append(f"{project['name']}: FAILED to send email")
                    
            except Exception as e:
                print(f"[EMAIL ERROR] Failed to send for {project['name']}: {e}")
                reminders_info.append(f"{project['name']}: FAILED - {str(e)}")
                
        except Exception as e:
            print(f"[REMINDER ERROR] Error processing project: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"[REMINDER] Complete: sent {sent_count} reminder(s)")
    
    return {
        "message": f"Sent {sent_count} reminder(s)", 
        "count": sent_count,
        "projects": reminders_info
    }

# --- Projects ---

@app.get("/projects")
def list_projects():
    return db.get_projects()

@app.post("/projects")
def create_project(project: ProjectCreate, background_tasks: BackgroundTasks):
    # 1. Create in DB (fast local write + background Supabase sync)
    new_project = db.create_project(project.dict())
    
    # 2. Trigger Folder Creation (in background)
    background_tasks.add_task(drive_service.find_or_create_folder, new_project['name'])
    
    # 3. Generate Standard Tasks - BATCH INSERT (much faster!)
    tasks_to_create = [
        {
            "title": std_task['title'],
            "project_id": new_project['id'],
            "code": std_task['code'],
            "category": std_task['category'],
            "status": "Upcoming"
        }
        for std_task in STANDARD_TASKS
    ]
    db.batch_create_tasks(tasks_to_create)  # Single operation instead of 20+

    # 4. Trigger Excel Update (in background)
    from services.excel_sync import ExcelSyncService
    excel_service = ExcelSyncService(drive_service)
    background_tasks.add_task(excel_service.sync_to_drive, db.get_projects(), db.get_tasks())
    
    # 5. Auto-check reminder if rig down is within 2 days
    rig_down_str = new_project.get('rig_down_date') or new_project.get('rig_down') or ''
    if rig_down_str:
        try:
            from datetime import datetime
            rig_down_date = datetime.strptime(rig_down_str, '%Y-%m-%d').date()
            days_until = (rig_down_date - datetime.now().date()).days
            
            if 0 <= days_until <= 2:
                print(f"[AUTO-REMINDER] Project {new_project['name']} has rig down in {days_until} days, sending alert NOW...")
                # Run reminder check immediately (not background) to ensure tasks are created
                email_service.send_project_rig_down_alert(new_project, days_until, len(tasks_to_create), is_new_project=True)
        except Exception as e:
            print(f"[AUTO-REMINDER] Error checking rig down date: {e}")
    
    return new_project

@app.patch("/projects/{project_id}")
def update_project(project_id: str, updates: dict):
    print(f"[UPDATE_PROJECT] Updating project {project_id} with: {updates}")
    result = db.update_project(project_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result

@app.get("/projects/{project_id}")
def get_project_details(project_id: str):
    print(f"[GET_PROJECT_DETAILS] Getting details for project_id: {project_id}")
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    tasks = db.get_tasks(project_id)
    
    # Sort tasks by code (e.g., 1.1, 1.2, 1.10, 2.1 - numeric order)
    def sort_key(task):
        code = task.get('code', '') or ''
        parts = code.split('.')
        # Convert each part to float for proper numeric sorting
        return [float(p) if p.replace('.', '').isdigit() else float('inf') for p in parts]
    
    tasks = sorted(tasks, key=sort_key)
    
    print(f"[GET_PROJECT_DETAILS] Found {len(tasks)} tasks for project {project_id}")
    return {"project": project, "tasks": tasks}

@app.delete("/projects/{project_id}")
def delete_project(project_id: str):
    """Delete a project and all its tasks (Admin only)"""
    print(f"[DELETE_PROJECT] Deleting project: {project_id}")
    
    # Get project to verify it exists
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete all tasks for this project first
    project_tasks = db.get_tasks(project_id)
    for task in project_tasks:
        db.delete_task(task['id'])
    
    # Delete the project using database method (works with Supabase)
    db.delete_project(project_id)
    
    print(f"[DELETE_PROJECT] Deleted project: {project['name']}")
    return {"status": "success", "deleted_project": project_id}

def compress_image_for_pdf(pil_image, max_width=1200, max_height=1600, quality=75):
    """Compress an image for PDF embedding to reduce file size.
    
    Args:
        pil_image: PIL Image object
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels  
        quality: JPEG quality (1-100, lower = smaller file)
    
    Returns:
        BytesIO buffer with compressed JPEG image
    """
    from PIL import Image as PILImage
    import io
    
    # Convert to RGB if necessary (for PNG with transparency)
    if pil_image.mode in ('RGBA', 'P'):
        # Create white background for transparent images
        background = PILImage.new('RGB', pil_image.size, (255, 255, 255))
        if pil_image.mode == 'P':
            pil_image = pil_image.convert('RGBA')
        background.paste(pil_image, mask=pil_image.split()[-1] if pil_image.mode == 'RGBA' else None)
        pil_image = background
    elif pil_image.mode != 'RGB':
        pil_image = pil_image.convert('RGB')
    
    # Resize if too large
    width, height = pil_image.size
    if width > max_width or height > max_height:
        ratio = min(max_width / width, max_height / height)
        new_size = (int(width * ratio), int(height * ratio))
        pil_image = pil_image.resize(new_size, PILImage.Resampling.LANCZOS)
    
    # Save as JPEG with compression
    output_buffer = io.BytesIO()
    pil_image.save(output_buffer, format='JPEG', quality=quality, optimize=True)
    output_buffer.seek(0)
    
    return output_buffer

@app.get("/projects/{project_id}/report")
def generate_project_report(project_id: str, mode: str = "download"):
    """Generate a comprehensive PDF report for a project with all attachments embedded
    
    Args:
        mode: 'download' to download file, 'preview' to view inline
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from PIL import Image as PILImage
    except ImportError:
        raise HTTPException(status_code=500, detail="ReportLab not installed. Run: pip install reportlab pillow")
    
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    tasks = db.get_tasks(project_id)
    
    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch, leftMargin=0.5*inch, rightMargin=0.5*inch)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontSize=28,
        spaceAfter=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#C41E3A')  # Weatherford Red
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontSize=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#666666'),
        spaceAfter=6
    )
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#C41E3A'),  # Weatherford Red
        spaceAfter=12,
        spaceBefore=20
    )
    
    elements = []
    
    # === TITLE PAGE ===
    elements.append(Spacer(1, 2*inch))
    elements.append(Paragraph("CSMS PROJECT REPORT", title_style))
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph(f"<b>{project['name']}</b>", ParagraphStyle(
        'ProjectName', fontSize=22, alignment=TA_CENTER, textColor=colors.black, spaceAfter=8
    )))
    
    # Well name prominently displayed below project name
    if project.get('well'):
        elements.append(Paragraph(f"Well: {project['well']}", ParagraphStyle(
            'WellName', fontSize=16, alignment=TA_CENTER, textColor=colors.HexColor('#C41E3A'), spaceAfter=16
        )))
    
    if project.get('title'):
        elements.append(Paragraph(project['title'], subtitle_style))
    
    elements.append(Spacer(1, 0.3*inch))
    
    # Project info table
    info_data = []
    if project.get('well'):
        info_data.append(['Well:', project['well']])
    if project.get('kontrak_no'):
        info_data.append(['Kontrak No:', project['kontrak_no']])
    if project.get('status'):
        info_data.append(['Status:', project['status']])
    if project.get('start_date'):
        info_data.append(['Start Date:', project['start_date']])
    if project.get('end_date'):
        info_data.append(['End Date:', project['end_date']])
    if project.get('rig_down'):
        info_data.append(['Rig Down:', project['rig_down']])
    if project.get('assigned_to'):
        info_data.append(['Assigned To:', project['assigned_to']])
    
    info_data.append(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M')])
    
    if info_data:
        info_table = Table(info_data, colWidths=[1.5*inch, 3*inch])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(info_table)
    
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph("PHM CSMS Project Management System", subtitle_style))
    
    # === TASKS AND ATTACHMENTS PAGE ===
    elements.append(PageBreak())
    elements.append(Paragraph("Task Summary & Attachments", heading_style))
    
    # Task statistics
    completed = len([t for t in tasks if t.get('status') == 'Completed'])
    total_attachments = sum(len(t.get('attachments', [])) for t in tasks)
    
    stats_data = [
        ['Total Tasks:', str(len(tasks))],
        ['Completed:', f"{completed} ({(completed/max(len(tasks),1)*100):.0f}%)"],
        ['Total Attachments:', str(total_attachments)]
    ]
    stats_table = Table(stats_data, colWidths=[1.5*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f5f5f5')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#ddd')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # List each task with attachments
    attachment_index = 0
    for task in tasks:
        task_code = task.get('code', '')
        task_title = task.get('title', 'Untitled')
        task_status = task.get('status', 'Upcoming')
        attachments = task.get('attachments', [])
        
        status_color = colors.HexColor('#46D369') if task_status == 'Completed' else colors.HexColor('#F5A623') if task_status == 'In Progress' else colors.HexColor('#666666')
        
        # Task header
        task_header = f"<b>{task_code}</b> - {task_title}"
        elements.append(Paragraph(task_header, ParagraphStyle(
            'TaskHeader', fontSize=11, textColor=colors.black, spaceBefore=12, spaceAfter=4
        )))
        elements.append(Paragraph(f"Status: <font color='#{status_color.hexval()[2:]}'>{task_status}</font>", ParagraphStyle(
            'TaskStatus', fontSize=9, textColor=colors.HexColor('#888888')
        )))
        
        # Process attachments - each on its own page with border
        if attachments:
            for att in attachments:
                attachment_index += 1
                filename = att.get('filename', 'Unknown')
                uploaded = att.get('uploaded_at', '')[:10] if att.get('uploaded_at') else ''
                file_ext = filename.lower().split('.')[-1] if '.' in filename else ''
                
                # Page break for each attachment
                elements.append(PageBreak())
                
                # Attachment header with border box
                header_table = Table(
                    [[f"Attachment {attachment_index}: {filename}", f"Uploaded: {uploaded}"]],
                    colWidths=[4.5*inch, 2*inch]
                )
                header_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E50914')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                    ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 11),
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ]))
                elements.append(header_table)
                elements.append(Spacer(1, 0.1*inch))
                
                try:
                    # Priority 1: Use stored file_id if available (INSTANT - for KMBR)
                    file_id = att.get('file_id')
                    
                    # Priority 2: Search for file (for new projects)
                    if not file_id:
                        file_id = drive_service.find_file_in_folder(filename, project['name'])
                    
                    if not file_id:
                        elements.append(Paragraph("<i>[File not found in Google Drive]</i>", ParagraphStyle(
                            'FileError', fontSize=10, textColor=colors.HexColor('#999999'), alignment=TA_CENTER, spaceBefore=50
                        )))
                        continue
                    
                    # Download file
                    file_data = drive_service.download_file(file_id)
                    if not file_data:
                        elements.append(Paragraph("<i>[Could not download file]</i>", ParagraphStyle(
                            'FileError', fontSize=10, textColor=colors.HexColor('#999999'), alignment=TA_CENTER, spaceBefore=50
                        )))
                        continue
                    
                    # Process based on file type
                    if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
                        # Compress image before embedding (reduces PDF size significantly)
                        img_buffer = io.BytesIO(file_data)
                        pil_img = PILImage.open(img_buffer)
                        
                        # Compress the image (max 1200x1600px, JPEG quality 75)
                        compressed_buffer = compress_image_for_pdf(pil_img, max_width=1200, max_height=1600, quality=75)
                        pil_img = PILImage.open(compressed_buffer)
                        
                        max_width = 6 * inch
                        max_height = 7.5 * inch
                        img_width, img_height = pil_img.size
                        scale = min(max_width / img_width, max_height / img_height, 1)
                        final_width = img_width * scale
                        final_height = img_height * scale
                        
                        compressed_buffer.seek(0)
                        rl_img = RLImage(compressed_buffer, width=final_width, height=final_height)
                        
                        # Wrap in table for border
                        img_table = Table([[rl_img]], colWidths=[final_width + 10])
                        img_table.setStyle(TableStyle([
                            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#333333')),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('TOPPADDING', (0, 0), (-1, -1), 5),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                        ]))
                        elements.append(img_table)
                        
                    elif file_ext == 'pdf':
                        # PDF - render pages with PyMuPDF
                        try:
                            import fitz
                            pdf_doc = fitz.open(stream=file_data, filetype='pdf')
                            total_pages = len(pdf_doc)
                            max_pages = min(20, total_pages)
                            
                            for page_num in range(max_pages):
                                if page_num > 0:
                                    elements.append(PageBreak())
                                    # Page continuation header
                                    cont_header = Table(
                                        [[f"{filename} - Page {page_num + 1} of {total_pages}"]],
                                        colWidths=[6.5*inch]
                                    )
                                    cont_header.setStyle(TableStyle([
                                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#444444')),
                                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('TOPPADDING', (0, 0), (-1, -1), 6),
                                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                                    ]))
                                    elements.append(cont_header)
                                    elements.append(Spacer(1, 0.1*inch))
                                
                                page = pdf_doc[page_num]
                                # Reduced DPI: Matrix(1.33, 1.33) = ~96 DPI vs Matrix(2, 2) = 144 DPI
                                mat = fitz.Matrix(1.33, 1.33)  # 96 DPI - good balance of quality/size
                                pix = page.get_pixmap(matrix=mat)
                                
                                # Convert to PIL and compress as JPEG
                                img_data = pix.tobytes("png")
                                img_buffer = io.BytesIO(img_data)
                                pil_img = PILImage.open(img_buffer)
                                
                                # Compress the rendered PDF page
                                compressed_buffer = compress_image_for_pdf(pil_img, max_width=1000, max_height=1400, quality=70)
                                pil_img = PILImage.open(compressed_buffer)
                                
                                max_width = 6.2 * inch
                                max_height = 8 * inch
                                img_width, img_height = pil_img.size
                                scale = min(max_width / img_width, max_height / img_height, 1)
                                final_width = img_width * scale
                                final_height = img_height * scale
                                
                                compressed_buffer.seek(0)
                                rl_img = RLImage(compressed_buffer, width=final_width, height=final_height)
                                
                                # Wrap in bordered table
                                img_table = Table([[rl_img]], colWidths=[final_width + 6])
                                img_table.setStyle(TableStyle([
                                    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#333333')),
                                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                                ]))
                                elements.append(img_table)
                            
                            pdf_doc.close()
                            
                            if total_pages > max_pages:
                                elements.append(Paragraph(f"<i>[Showing first {max_pages} of {total_pages} pages]</i>", ParagraphStyle(
                                    'PageNote', fontSize=9, textColor=colors.HexColor('#888888'), alignment=TA_CENTER, spaceBefore=10
                                )))
                                
                        except Exception as e:
                            print(f"[WARN] PyMuPDF PDF error {filename}: {e}")
                            elements.append(Paragraph(f"<i>[PDF preview not available]</i>", ParagraphStyle(
                                'FileNote', fontSize=10, textColor=colors.HexColor('#666666'), alignment=TA_CENTER, spaceBefore=50
                            )))
                    
                    elif file_ext in ['xlsx', 'xls', 'docx', 'doc', 'pptx', 'ppt']:
                        # Office files - convert to PDF using Google Drive, then render
                        try:
                            import fitz
                            
                            # Convert Office file to PDF via Google Drive
                            pdf_data = drive_service.convert_office_to_pdf(file_id, filename)
                            
                            if pdf_data:
                                # Render the converted PDF
                                pdf_doc = fitz.open(stream=pdf_data, filetype='pdf')
                                total_pages = len(pdf_doc)
                                max_pages = min(20, total_pages)
                                
                                for page_num in range(max_pages):
                                    if page_num > 0:
                                        elements.append(PageBreak())
                                        # Page continuation header
                                        cont_header = Table(
                                            [[f"{filename} - Page {page_num + 1} of {total_pages}"]],
                                            colWidths=[6.5*inch]
                                        )
                                        cont_header.setStyle(TableStyle([
                                            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#444444')),
                                            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                                            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                                            ('FONTSIZE', (0, 0), (-1, -1), 10),
                                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                            ('TOPPADDING', (0, 0), (-1, -1), 6),
                                            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                                        ]))
                                        elements.append(cont_header)
                                        elements.append(Spacer(1, 0.1*inch))
                                    
                                    page = pdf_doc[page_num]
                                    # Reduced DPI for smaller file size
                                    mat = fitz.Matrix(1.33, 1.33)  # 96 DPI
                                    pix = page.get_pixmap(matrix=mat)
                                    
                                    # Convert and compress as JPEG
                                    img_data = pix.tobytes("png")
                                    img_buffer = io.BytesIO(img_data)
                                    pil_img = PILImage.open(img_buffer)
                                    
                                    # Compress the rendered page
                                    compressed_buffer = compress_image_for_pdf(pil_img, max_width=1000, max_height=1400, quality=70)
                                    pil_img = PILImage.open(compressed_buffer)
                                    
                                    max_width = 6.2 * inch
                                    max_height = 8 * inch
                                    img_width, img_height = pil_img.size
                                    scale = min(max_width / img_width, max_height / img_height, 1)
                                    final_width = img_width * scale
                                    final_height = img_height * scale
                                    
                                    compressed_buffer.seek(0)
                                    rl_img = RLImage(compressed_buffer, width=final_width, height=final_height)
                                    
                                    # Wrap in bordered table
                                    img_table = Table([[rl_img]], colWidths=[final_width + 6])
                                    img_table.setStyle(TableStyle([
                                        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#333333')),
                                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                                    ]))
                                    elements.append(img_table)
                                
                                pdf_doc.close()
                                
                                if total_pages > max_pages:
                                    elements.append(Paragraph(f"<i>[Showing first {max_pages} of {total_pages} pages]</i>", ParagraphStyle(
                                        'PageNote', fontSize=9, textColor=colors.HexColor('#888888'), alignment=TA_CENTER, spaceBefore=10
                                    )))
                            else:
                                # Conversion failed - show placeholder
                                elements.append(Paragraph(f"<i>[Could not convert {file_ext.upper()} file - stored in Google Drive]</i>", ParagraphStyle(
                                    'FileNote', fontSize=10, textColor=colors.HexColor('#666666'), alignment=TA_CENTER, spaceBefore=50
                                )))
                                
                        except Exception as e:
                            print(f"[WARN] Office conversion error {filename}: {e}")
                            elements.append(Paragraph(f"<i>[Document conversion failed]</i>", ParagraphStyle(
                                'FileNote', fontSize=10, textColor=colors.HexColor('#666666'), alignment=TA_CENTER, spaceBefore=50
                            )))
                    else:
                        # Unknown file type
                        elements.append(Paragraph(f"<i>[File type {file_ext.upper()} - stored in Google Drive]</i>", ParagraphStyle(
                            'FileNote', fontSize=10, textColor=colors.HexColor('#666666'), alignment=TA_CENTER, spaceBefore=50
                        )))
                        
                except Exception as e:
                    print(f"[WARN] Could not process attachment {filename}: {e}")
                    elements.append(Paragraph(f"<i>[Error processing file]</i>", ParagraphStyle(
                        'FileError', fontSize=10, textColor=colors.HexColor('#999999'), alignment=TA_CENTER, spaceBefore=50
                    )))
        else:
            elements.append(Paragraph("<i>No attachments for this task</i>", ParagraphStyle(
                'NoAttachment', fontSize=10, textColor=colors.HexColor('#999999'), leftIndent=20
            )))
    
    # === FOOTER ===
    elements.append(Spacer(1, 0.5*inch))
    elements.append(Paragraph(
        "<i>Generated by CSMS Project Management System - PHM</i>",
        ParagraphStyle('FootNote', fontSize=9, textColor=colors.HexColor('#888888'), alignment=TA_CENTER)
    ))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"{project['name'].replace(' ', '_')}_Report.pdf"
    
    # Return based on mode
    disposition = "inline" if mode == "preview" else "attachment"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"{disposition}; filename={filename}"}
    )

# --- Tasks ---

@app.post("/tasks")
def create_task(task: dict):
    """Create a new task and assign it to a project"""
    print(f"[CREATE_TASK] Received task data: {task}")
    
    project_id = task.get('project_id')
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    
    # Check if project exists
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    
    # Generate a unique task ID
    import uuid
    task_id = str(uuid.uuid4())[:8]
    
    # Create the task
    new_task = {
        "id": task_id,
        "project_id": project_id,
        "code": task.get('code', ''),
        "title": task.get('title', ''),
        "well_name": task.get('well_name', project.get('well_name', '')),
        "category": task.get('category', ''),
        "status": task.get('status', 'Upcoming'),
        "description": task.get('description', ''),
        "start_date": task.get('start_date'),
        "end_date": task.get('end_date'),
        "attachments": [],
        "created_at": datetime.now().isoformat()
    }
    
    # Save task to database
    saved_task = db.create_task(new_task)
    print(f"[CREATE_TASK] Task created: {saved_task}")
    return saved_task

@app.get("/tasks")
def list_tasks(status: Optional[str] = None):
    # This is for the "All Tasks" gallery, possibly filtered
    all_tasks = db.get_tasks()
    if status:
        return [t for t in all_tasks if t.get('status') == status]
    return all_tasks


@app.put("/tasks/{task_id}")
def update_task(task_id: str, task_update: dict):
    print(f"[UPDATE_TASK] Task ID: {task_id}")
    print(f"[UPDATE_TASK] Updates received: {task_update}")
    updated = db.update_task(task_id, task_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    print(f"[UPDATE_TASK] Updated task: {updated}")
    return updated

@app.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    """Delete a task (Admin only)"""
    print(f"[DELETE_TASK] Deleting task: {task_id}")
    
    all_tasks = db.get_tasks()
    task_to_delete = next((t for t in all_tasks if t.get('id') == task_id), None)
    
    if not task_to_delete:
        raise HTTPException(status_code=404, detail="Task not found")
    
    remaining_tasks = [t for t in all_tasks if t.get('id') != task_id]
    
    import os
    tasks_file = os.path.join(os.path.dirname(__file__), "data", "tasks.json")
    db._write_json(tasks_file, remaining_tasks)
    
    print(f"[DELETE_TASK] Deleted task: {task_to_delete.get('code', task_id)}")
    return {"status": "success", "deleted_task": task_id}

@app.get("/debug/task/{task_id}")
def debug_task(task_id: str):
    """Debug endpoint to check current task status in database"""
    import os
    tasks_file = os.path.join(os.path.dirname(__file__), "data", "tasks.json")
    print(f"[DEBUG] Reading tasks from: {tasks_file}")
    print(f"[DEBUG] File exists: {os.path.exists(tasks_file)}")
    
    tasks = db.get_tasks()
    task = next((t for t in tasks if t['id'] == task_id), None)
    if task:
        return {"task_id": task_id, "status": task.get('status'), "full_task": task}
    return {"error": "Task not found", "task_id": task_id}

@app.get("/debug/supabase-status")
def debug_supabase_status():
    """Check if Supabase is enabled and reachable"""
    from services.supabase_service import supabase_service
    status = {
        "enabled": supabase_service.enabled,
        "url_configured": bool(supabase_service.url),
        "key_configured": bool(supabase_service.key),
        "client_initialized": bool(supabase_service.client),
        "projects_count": len(supabase_service.get_projects()) if supabase_service.enabled else "N/A"
    }
    return status

@app.get("/debug/drive-status")
def debug_drive_status():
    """Check Google Drive service status for remote debugging"""
    return {
        "enabled": drive_service.enabled,
        "auth_method": getattr(drive_service, 'auth_method', None),
        "folder_id": drive_service.folder_id[:20] + "..." if drive_service.folder_id else "NOT SET",
        "token_json_set": bool(drive_service.token_json),
        "token_json_length": len(drive_service.token_json),
        "service_account_set": bool(getattr(drive_service, 'service_account_json', '')),
        "service_account_length": len(getattr(drive_service, 'service_account_json', '')),
        "service_initialized": drive_service.service is not None
    }

@app.post("/tasks/{task_id}/upload")
async def upload_attachment(
    task_id: str, 
    file: UploadFile = File(...)
):
    # 1. Get Task & Project info
    tasks = db.get_tasks()
    task = next((t for t in tasks if t['id'] == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project = db.get_project(task['project_id'])
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Read file content
    content = await file.read()
    
    # 3. Upload to Drive with nested folder structure based on task code
    task_code = task.get('code', '')
    task_title = task.get('title', '')
    print(f"[UPLOAD DEBUG] Task ID: {task_id}")
    print(f"[UPLOAD DEBUG] Task object: {task}")
    print(f"[UPLOAD DEBUG] Task code value: '{task_code}'")
    print(f"[UPLOAD DEBUG] Task title: '{task_title}'")
    print(f"[UPLOAD DEBUG] Project name: {project['name']}")
    
    result = await drive_service.upload_file_to_drive(
        file_data=content, 
        filename=file.filename, 
        project_name=project['name'],
        task_code=task_code,
        task_title=task_title
    )
    
    if not result.get('success'):
        raise HTTPException(status_code=500, detail="Failed to upload to Drive")
        
    # 4. Update Task with attachment info including file_id for faster retrieval
    current_attachments = task.get("attachments", [])
    current_attachments.append({
        "filename": file.filename,
        "file_id": result.get('file_id'),  # Store file_id for direct access
        "folder_path": result.get('folder_path'),  # Store path for debugging
        "uploaded_at": datetime.now().isoformat()
    })
    db.update_task(task_id, {"attachments": current_attachments})
    
    print(f"[UPLOAD] Attachment saved: {file.filename} -> {result.get('folder_path')}")
    return {"status": "success", "filename": file.filename, "file_id": result.get('file_id')}

# --- Schedules ---

@app.get("/schedules")
def list_schedules():
    return get_schedules()

@app.post("/schedules")
def create_schedule_route(schedule: ScheduleCreate, background_tasks: BackgroundTasks):
    import uuid
    
    # Create schedule data
    new_schedule = {
        "id": str(uuid.uuid4()),
        **schedule.dict(),
        "created_at": datetime.now().isoformat()
    }
    
    # SYNCHRONOUS save - will fail loudly if Supabase fails
    save_schedule(new_schedule)
    print(f"[SCHEDULE] Created schedule: {new_schedule['id']}")
    print(f"[DEBUG_SCHEDULE] Data: {json.dumps(new_schedule, default=str)}")

    
    # Send email notification in background
    # Send email notification immediately (Synchronous for Vercel reliability)
    try:
        email_service.send_schedule_notification(new_schedule)
        print(f"[EMAIL] Notification sent for schedule {new_schedule['id']}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send notification: {e}")
    
    return new_schedule

@app.delete("/schedules/{schedule_id}")
def delete_schedule_route(schedule_id: str):
    """Delete a schedule (Admin only)"""
    print(f"[DELETE_SCHEDULE] Deleting schedule: {schedule_id}")
    
    # SYNCHRONOUS delete - will fail loudly if Supabase fails
    delete_schedule(schedule_id)
    
    print(f"[DELETE_SCHEDULE] Deleted schedule: {schedule_id}")
    return {"status": "success", "deleted_schedule": schedule_id}

# --- CSMS PB Status ---

@app.get("/csms-pb")
def list_csms_pb():
    """Get all CSMS PB records"""
    return get_csms_pb_records()

@app.post("/csms-pb")
def create_csms_pb_route(pb: CSMSPBCreate):
    """Create a new CSMS PB record"""
    import uuid
    
    new_pb = {
        "id": str(uuid.uuid4()),
        **pb.dict(),
        "attachments": [],
        "created_at": datetime.now().isoformat()
    }
    
    # SYNCHRONOUS save - will fail loudly if Supabase fails
    save_csms_pb(new_pb)
    print(f"[CSMS_PB] Created PB record: {new_pb['id']}")
    
    return new_pb

@app.delete("/csms-pb/{pb_id}")
def delete_csms_pb_route(pb_id: str):
    """Delete a CSMS PB record (Admin only)"""
    print(f"[DELETE_PB] Deleting PB record: {pb_id}")
    
    # SYNCHRONOUS delete - will fail loudly if Supabase fails
    delete_csms_pb(pb_id)
    
    print(f"[DELETE_PB] Deleted PB record: {pb_id}")
    return {"status": "success", "deleted_pb": pb_id}


@app.post("/csms-pb/{pb_id}/attachment")
async def upload_csms_pb_attachment(pb_id: str, file: UploadFile = File(...)):
    """Upload attachment to a CSMS PB record"""
    records = get_csms_pb_records()
    pb_record = next((r for r in records if r['id'] == pb_id), None)
    
    if not pb_record:
        raise HTTPException(status_code=404, detail="PB record not found")
    
    # Save file to Google Drive
    try:
        file_content = await file.read()
        file_id = drive_service.upload_file(file.filename, file_content)
        
        attachment = {
            "filename": file.filename,
            "drive_file_id": file_id,
            "uploaded_at": datetime.now().isoformat()
        }
        
        if 'attachments' not in pb_record:
            pb_record['attachments'] = []
        pb_record['attachments'].append(attachment)
        
        save_csms_pb_records(records)
        return {"status": "success", "attachment": attachment}
    except Exception as e:
        print(f"[ERROR] Failed to upload PB attachment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/csms-pb/statistics")
def get_csms_pb_statistics():
    """Get CSMS PB statistics for dashboard"""
    records = get_csms_pb_records()
    projects = db.get_projects()
    
    # Group by project
    project_scores = {}
    for record in records:
        pid = record.get('project_id')
        if pid not in project_scores:
            project_scores[pid] = []
        project_scores[pid].append(record.get('score', 0))
    
    # Calculate stats per project
    stats = []
    for pid, scores in project_scores.items():
        project = next((p for p in projects if p['id'] == pid), {})
        avg_score = sum(scores) / len(scores) if scores else 0
        latest_score = scores[-1] if scores else 0
        
        stats.append({
            "project_id": pid,
            "project_name": project.get('name', 'Unknown'),
            "well_name": project.get('well_name', ''),
            "average_score": round(avg_score, 1),
            "latest_score": latest_score,
            "record_count": len(scores),
            "status": "critical" if latest_score < 60 else ("warning" if latest_score < 80 else "good")
        })
    
    return stats

# --- Related Documents ---

@app.get("/related-docs")
def list_related_docs():
    """Get all related documents"""
    return get_related_docs()

@app.post("/related-docs")
async def create_related_doc(
    project_id: str = Form(...),
    well_name: str = Form(None),
    doc_name: str = Form(...),
    file: UploadFile = File(...)
):
    """Create a new related document with file upload"""
    import uuid
    
    # Upload to Google Drive
    try:
        file_content = await file.read()
        
        # Upload to "RelatedDocs" subfolder
        file_id = drive_service.upload_file(file.filename, file_content, "RelatedDocs")
        
        if not file_id:
            raise Exception("Failed to upload file to Google Drive")
        
        new_doc = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "well_name": well_name,
            "doc_name": doc_name,
            "filename": file.filename,
            "drive_file_id": file_id,
            "created_at": datetime.now().isoformat()
        }
        
        # SYNCHRONOUS save - will fail loudly if Supabase fails
        save_related_doc(new_doc)
        print(f"[RELATED_DOC] Created: {new_doc['id']}")
        
        return new_doc
    except Exception as e:
        print(f"[ERROR] Failed to upload related doc: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/related-docs/{doc_id}")
def delete_related_doc_route(doc_id: str):
    """Delete a related document"""
    # SYNCHRONOUS delete - will fail loudly if Supabase fails
    delete_related_doc(doc_id)
    print(f"[RELATED_DOC] Deleted: {doc_id}")
    
    return {"status": "deleted"}

@app.get("/download/{file_id}")
async def download_drive_file(file_id: str):
    """Download a file from Google Drive by its ID"""
    try:
        import io
        from googleapiclient.http import MediaIoBaseDownload
        
        # Get file metadata first
        file_metadata = drive_service.service.files().get(fileId=file_id, fields='name, mimeType').execute()
        filename = file_metadata.get('name', 'download')
        mime_type = file_metadata.get('mimeType', 'application/octet-stream')
        
        print(f"[DOWNLOAD] Downloading file: {filename} ({mime_type})")
        
        # Download the file
        request = drive_service.service.files().get_media(fileId=file_id)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        file_buffer.seek(0)
        
        return StreamingResponse(
            file_buffer,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        print(f"[DOWNLOAD ERROR] {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=404, detail=f"File not found or download failed: {str(e)}")

# --- Rig Down Reminder System ---

def send_rig_down_reminder(project: dict, completion_percentage: float, incomplete_tasks: list):
    """Send reminder email for rig down deadline via Brevo API"""
    
    try:
        # Use existing email_service which uses BREVO_API_KEY
        # No need for SMTP_EMAIL/PASSWORD anymore
        
        if not project.get('pic_email'):
            print(f"[REMINDER] Missing PIC email for {project['name']}")
            return False
            
        # Parse recipients (handle commas)
        pic_email_str = project.get('pic_email', '')
        recipients = [e.strip() for e in pic_email_str.split(',') if e.strip()]
        
        if not recipients:
             return False

        days_until = "0-2" # This function is called when it's imminent
        # Ideally pass days_until, but for now we stick to the signature or infer it?
        # The caller (check_and_send_reminders) calculates days_until. 
        # But this function doesn't take it as arg. 
        # Converting logic to match the existing body style but using email_service.
        
        rig_down_str = project.get('rig_down') or 'N/A'
        
        subject = f"⚠️ URGENT: Rig Down Deadline Approaching - {project['name']}"
        
        task_list = "".join([f"<li>{t['code']}: {t['title']}</li>" for t in incomplete_tasks[:10]])
        remaining_count = len(incomplete_tasks) - 10
        more_text = f"<p><em>...and {remaining_count} more</em></p>" if remaining_count > 0 else ""
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: #FF6B35; color: white; padding: 20px; border-radius: 8px;">
                <h2 style="margin: 0;">⚠️ Rig Down Deadline Reminder</h2>
            </div>
            <div style="padding: 20px; background: #f5f5f5; border-radius: 8px; margin-top: 10px;">
                <p>Dear PIC,</p>
                <p><strong>Rig Down Date:</strong> {rig_down_str}</p>
                <p><strong>Project:</strong> {project['name']}</p>
                <p><strong>Well:</strong> {project.get('well', 'N/A')}</p>
                
                <div style="background: #E50914; color: white; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="margin: 0;">Task Completion: {completion_percentage:.1f}%</h3>
                    <p style="margin: 5px 0 0 0;">Required: 95% - Current: {completion_percentage:.1f}%</p>
                </div>
                
                <p><strong>Incomplete Tasks ({len(incomplete_tasks)}):</strong></p>
                <ul>{task_list}</ul>
                {more_text}
                
                <p style="color: #E50914; font-weight: bold;">Please complete the remaining tasks before the Rig Down date.</p>
                
                <p>Best regards,<br><strong>CSMS Project Management System</strong><br>PHM</p>
            </div>
        </body>
        </html>
        """
        
        # Call the global email_service
        return email_service._send_email(recipients, subject, body_html)
        
    except Exception as e:
        print(f"[REMINDER ERROR] {e}")
        return False

@app.get("/check-reminders")
def check_and_send_reminders(background_tasks: BackgroundTasks):
    """Check projects approaching rig down and send reminders if tasks < 95% complete"""
    today = datetime.now().date()
    reminders_sent = []
    
    projects = db.get_projects()
    all_tasks = db.get_tasks()
    
    for project in projects:
        rig_down = project.get('rig_down')
        if not rig_down or not project.get('pic_email'):
            continue
        
        try:
            rig_down_date = datetime.strptime(rig_down, '%Y-%m-%d').date()
            days_until = (rig_down_date - today).days
            
            # Check if 2 days before rig down
            if days_until <= 2 and days_until >= 0:
                # Get project tasks
                project_tasks = [t for t in all_tasks if t.get('project_id') == project['id']]
                
                if len(project_tasks) == 0:
                    continue
                
                completed = len([t for t in project_tasks if t.get('status') == 'Completed'])
                completion_pct = (completed / len(project_tasks)) * 100
                
                # Send reminder if less than 95% complete
                if completion_pct < 95:
                    incomplete = [t for t in project_tasks if t.get('status') != 'Completed']
                    background_tasks.add_task(send_rig_down_reminder, project, completion_pct, incomplete)
                    reminders_sent.append({
                        "project": project['name'],
                        "rig_down": rig_down,
                        "completion": completion_pct,
                        "pic_email": project['pic_email']
                    })
        except Exception as e:
            print(f"[REMINDER] Error checking project {project['name']}: {e}")
    
    return {"reminders_sent": len(reminders_sent), "details": reminders_sent}

# --- Comments API ---

@app.get("/comments")
def list_comments():
    """Get all comments for home screen status updates"""
    comments = get_comments()
    # Sort by creation date, newest first
    comments.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return comments

@app.post("/comments")
def create_comment_route(comment: CommentCreate):
    """Create a new comment/status update"""
    import uuid
    
    new_comment = {
        "id": str(uuid.uuid4()),
        "author_name": comment.author_name,
        "content": comment.content,
        "attachment_filename": comment.attachment_filename,
        "attachment_data": comment.attachment_data,  # Base64 data URL for images
        "created_at": datetime.now().isoformat(),
        "likes": 0,
        "replies": []
    }
    
    # SYNCHRONOUS save - will fail loudly if Supabase fails
    save_comment(new_comment)
    print(f"[COMMENT] New comment by {comment.author_name}")
    print(f"[DEBUG_COMMENT] Has Attachment: {bool(comment.attachment_data)}")
    if comment.attachment_data:
        print(f"[DEBUG_COMMENT] Attachment Size: {len(comment.attachment_data)} bytes")

    
    return new_comment

@app.delete("/comments/{comment_id}")
def delete_comment_route(comment_id: str):
    """Delete a comment (Admin only)"""
    print(f"[DELETE_COMMENT] Deleting comment: {comment_id}")
    
    # SYNCHRONOUS delete - will fail loudly if Supabase fails
    delete_comment(comment_id)
    
    print(f"[DELETE_COMMENT] Deleted comment: {comment_id}")
    return {"status": "success", "deleted_comment": comment_id}

class ReplyCreate(BaseModel):
    author_name: str = "User"
    content: str
    attachment_filename: Optional[str] = None
    attachment_data: Optional[str] = None

@app.post("/comments/{comment_id}/replies")
def add_reply(comment_id: str, reply: ReplyCreate):
    """Add a reply to a comment"""
    import uuid
    
    comments = get_comments()
    comment = next((c for c in comments if c.get('id') == comment_id), None)
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    new_reply = {
        "id": str(uuid.uuid4()),
        "author_name": reply.author_name,
        "content": reply.content,
        "attachment_filename": reply.attachment_filename,
        "attachment_data": reply.attachment_data,
        "created_at": datetime.now().isoformat()
    }
    
    if 'replies' not in comment:
        comment['replies'] = []
    comment['replies'].append(new_reply)
    
    # SYNCHRONOUS update - will fail loudly if Supabase fails
    update_comment(comment_id, {"replies": comment['replies']})
    
    print(f"[REPLY] New reply by {reply.author_name} to comment {comment_id}")
    return new_reply

@app.post("/comments/{comment_id}/like")
def like_comment_route(comment_id: str):
    """Like a comment (increment likes counter)"""
    comments = get_comments()
    comment = next((c for c in comments if c.get('id') == comment_id), None)
    
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    new_likes = comment.get('likes', 0) + 1
    
    # SYNCHRONOUS update - will fail loudly if Supabase fails
    update_comment(comment_id, {"likes": new_likes})
    
    print(f"[LIKE] Comment {comment_id} liked, now has {new_likes} likes")
    return {"status": "success", "likes": new_likes}

# --- Statistics API ---

@app.get("/statistics")
def get_statistics():
    """Get comprehensive statistics for dashboard"""
    projects = db.get_projects()
    tasks = db.get_tasks()
    schedules = get_schedules()
    
    # Project stats
    project_stats = {
        "total": len(projects),
        "by_status": {
            "Upcoming": len([p for p in projects if p.get('status') == 'Upcoming']),
            "InProgress": len([p for p in projects if p.get('status') in ['InProgress', 'Ongoing']]),
            "Completed": len([p for p in projects if p.get('status') == 'Completed']),
            "OnHold": len([p for p in projects if p.get('status') == 'OnHold'])
        }
    }
    
    # Task stats
    task_stats = {
        "total": len(tasks),
        "by_status": {
            "Upcoming": len([t for t in tasks if t.get('status') == 'Upcoming']),
            "In Progress": len([t for t in tasks if t.get('status') == 'In Progress']),
            "Completed": len([t for t in tasks if t.get('status') == 'Completed'])
        },
        "completion_rate": (len([t for t in tasks if t.get('status') == 'Completed']) / max(len(tasks), 1)) * 100,
        "with_attachments": len([t for t in tasks if t.get('attachments') and len(t['attachments']) > 0])
    }
    
    # Schedule stats - handle None values for different schedule types
    today = datetime.now().date()
    
    def safe_parse_date(date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                return None
        return None
    
    upcoming_mwt = [s for s in schedules if s.get('mwt_plan_date') and safe_parse_date(s['mwt_plan_date']) and safe_parse_date(s['mwt_plan_date']) >= today]
    upcoming_hse = [s for s in schedules if s.get('hse_meeting_date') and safe_parse_date(s['hse_meeting_date']) and safe_parse_date(s['hse_meeting_date']) >= today]
    
    # Count all schedule types for this month
    this_month_count = 0
    for s in schedules:
        for field in ['mwt_plan_date', 'hse_meeting_date', 'csms_pb_date', 'hseplan_date', 'spr_date', 'hazid_date']:
            date_val = safe_parse_date(s.get(field))
            if date_val and date_val.month == today.month and date_val.year == today.year:
                this_month_count += 1
                break
    
    schedule_stats = {
        "total": len(schedules),
        "upcoming_mwt": len(upcoming_mwt),
        "upcoming_hse": len(upcoming_hse),
        "this_month": this_month_count
    }
    
    # Project completion breakdown by project
    project_completion = []
    for p in projects[:10]:  # Top 10
        proj_tasks = [t for t in tasks if t.get('project_id') == p['id']]
        completed = len([t for t in proj_tasks if t.get('status') == 'Completed'])
        total = len(proj_tasks)
        project_completion.append({
            "name": p['name'][:20],
            "completed": completed,
            "total": total,
            "percentage": (completed / max(total, 1)) * 100
        })
    
    return {
        "projects": project_stats,
        "tasks": task_stats,
        "schedules": schedule_stats,
        "project_completion": project_completion
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
