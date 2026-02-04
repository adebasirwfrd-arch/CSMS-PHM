"""
Supabase Database Layer
- Supabase is the MANDATORY SINGLE SOURCE OF TRUTH
- Local JSON fallback removed for Vercel compatibility
"""
import os
from typing import List, Dict, Optional
import uuid
from datetime import datetime

# Import Supabase service
try:
    from services.supabase_service import supabase_service
    # Ensure it's enabled
    if not supabase_service or not supabase_service.enabled:
        print("[CRITICAL] Supabase is NOT enabled. Application will fail on Vercel.")
        SUPABASE_ENABLED = False
    else:
        SUPABASE_ENABLED = True
except ImportError:
    print("[CRITICAL] Could not import supabase_service.")
    supabase_service = None
    SUPABASE_ENABLED = False

# Local data paths (Deprecated/Removed for write operations)
# We keep these as strings for backward compatibility in imports if needed, 
# but we will NOT write to them.
DATA_DIR = "/tmp" # Use /tmp if local storage is absolutely needed for short-lived temp files
TASKS_FILE = "" 
PROJECTS_FILE = ""
SCHEDULES_FILE = ""
COMMENTS_FILE = ""
CSMS_PB_FILE = ""
RELATED_DOCS_FILE = ""


class Database:
    """
    Supabase Database - Single source of truth.
    Local JSON fallback has been removed.
    """
    
    def __init__(self):
        if not SUPABASE_ENABLED:
            print("[WARN] Database initialized without Supabase. Most operations will fail.")

    def _read_json(self, filepath) -> List[Dict]:
        return []

    def _write_json(self, filepath, data: List[Dict]):
        print(f"[DB] Skipping local write to {filepath} (Read-only filesystem)")
        pass

    # ==================== PROJECTS ====================
    
    def get_projects(self) -> List[Dict]:
        if SUPABASE_ENABLED:
            return supabase_service.get_projects()
        return []

    def get_project(self, project_id: str) -> Optional[Dict]:
        if SUPABASE_ENABLED:
            return supabase_service.get_project(project_id)
        return None

    def create_project(self, project_data: Dict) -> Dict:
        if SUPABASE_ENABLED:
            return supabase_service.create_project(project_data)
        return project_data

    def update_project(self, project_id: str, updates: Dict) -> Optional[Dict]:
        if SUPABASE_ENABLED:
            return supabase_service.update_project(project_id, updates)
        return None

    def delete_project(self, project_id: str) -> bool:
        if SUPABASE_ENABLED:
            return supabase_service.delete_project(project_id)
        return False

    # ==================== TASKS ====================
    
    def get_tasks(self, project_id: str = None) -> List[Dict]:
        if SUPABASE_ENABLED:
            return supabase_service.get_tasks(project_id)
        return []

    def create_task(self, task_data: Dict) -> Dict:
        if SUPABASE_ENABLED:
            return supabase_service.create_task(task_data)
        return task_data
    
    def batch_create_tasks(self, tasks_data: List[Dict]) -> List[Dict]:
        if SUPABASE_ENABLED:
            return supabase_service.batch_create_tasks(tasks_data)
        return tasks_data

    def update_task(self, task_id: str, updates: Dict) -> Optional[Dict]:
        if SUPABASE_ENABLED:
            return supabase_service.update_task(task_id, updates)
        return None

    def delete_task(self, task_id: str) -> bool:
        if SUPABASE_ENABLED:
            return supabase_service.delete_task(task_id)
        return False


# ==================== HELPER FUNCTIONS ====================

def get_schedules() -> List[Dict]:
    if SUPABASE_ENABLED:
        return supabase_service.get_schedules()
    return []

def save_schedule(schedule: Dict):
    if SUPABASE_ENABLED:
        return supabase_service.save_schedule(schedule)

def delete_schedule(schedule_id: str):
    if SUPABASE_ENABLED:
        return supabase_service.delete_schedule(schedule_id)

def save_schedules(schedules: List[Dict]):
    pass

def get_comments() -> List[Dict]:
    if SUPABASE_ENABLED:
        return supabase_service.get_comments()
    return []

def save_comment(comment: Dict):
    if SUPABASE_ENABLED:
        return supabase_service.save_comment(comment)

def update_comment(comment_id: str, updates: Dict):
    if SUPABASE_ENABLED:
        return supabase_service.update_comment(comment_id, updates)

def delete_comment(comment_id: str):
    if SUPABASE_ENABLED:
        return supabase_service.delete_comment(comment_id)

def save_comments(comments: List[Dict]):
    pass

def get_csms_pb_records() -> List[Dict]:
    if SUPABASE_ENABLED:
        return supabase_service.get_csms_pb_records()
    return []

def save_csms_pb(pb: Dict):
    if SUPABASE_ENABLED:
        return supabase_service.save_csms_pb(pb)

def update_csms_pb(pb_id: str, updates: Dict):
    if SUPABASE_ENABLED:
        return supabase_service.update_csms_pb(pb_id, updates)

def delete_csms_pb(pb_id: str):
    if SUPABASE_ENABLED:
        return supabase_service.delete_csms_pb(pb_id)

def save_csms_pb_records(records: List[Dict]):
    pass

def get_related_docs() -> List[Dict]:
    if SUPABASE_ENABLED:
        return supabase_service.get_related_docs()
    return []

def save_related_doc(doc: Dict):
    if SUPABASE_ENABLED:
        return supabase_service.save_related_doc(doc)

def delete_related_doc(doc_id: str):
    if SUPABASE_ENABLED:
        return supabase_service.delete_related_doc(doc_id)

def save_related_docs(docs: List[Dict]):
    pass
