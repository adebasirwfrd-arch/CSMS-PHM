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
            print("[CRITICAL] Database initialized WITHOUT Supabase. All cloud operations will fail!")
        else:
            print("[OK] Database initialized with Supabase as single source of truth.")

    def _read_json(self, filepath) -> List[Dict]:
        return []

    def _write_json(self, filepath, data: List[Dict]):
        # Just log it once so we know something is still trying to write local files
        print(f"[ERROR/VERCEL] Blocked direct write attempt to: {filepath}")
        pass

    # ==================== PROJECTS ====================
    
    def get_projects(self) -> List[Dict]:
        if not SUPABASE_ENABLED: return []
        try:
            return supabase_service.get_projects()
        except Exception as e:
            print(f"[DB ERROR] get_projects failed: {e}")
            return []

    def get_project(self, project_id: str) -> Optional[Dict]:
        if not SUPABASE_ENABLED: return None
        try:
            return supabase_service.get_project(project_id)
        except Exception as e:
            print(f"[DB ERROR] get_project({project_id}) failed: {e}")
            return None

    def create_project(self, project_data: Dict) -> Dict:
        if not SUPABASE_ENABLED: return project_data
        try:
            print(f"[DB INFO] Creating project: {project_data.get('name')}")
            return supabase_service.create_project(project_data)
        except Exception as e:
            print(f"[DB ERROR] create_project failed: {e}")
            return project_data

    def update_project(self, project_id: str, updates: Dict) -> Optional[Dict]:
        if not SUPABASE_ENABLED: return None
        try:
            print(f"[DB INFO] Updating project {project_id}")
            return supabase_service.update_project(project_id, updates)
        except Exception as e:
            print(f"[DB ERROR] update_project({project_id}) failed: {e}")
            return None

    def delete_project(self, project_id: str) -> bool:
        if not SUPABASE_ENABLED: return False
        try:
            print(f"[DB INFO] Deleting project {project_id}")
            return supabase_service.delete_project(project_id)
        except Exception as e:
            print(f"[DB ERROR] delete_project({project_id}) failed: {e}")
            return False

    # ==================== TASKS ====================
    
    def get_tasks(self, project_id: str = None) -> List[Dict]:
        if not SUPABASE_ENABLED: return []
        try:
            return supabase_service.get_tasks(project_id)
        except Exception as e:
            print(f"[DB ERROR] get_tasks failed: {e}")
            return []

    def create_task(self, task_data: Dict) -> Dict:
        if not SUPABASE_ENABLED: return task_data
        try:
            return supabase_service.create_task(task_data)
        except Exception as e:
            print(f"[DB ERROR] create_task failed: {e}")
            return task_data
    
    def batch_create_tasks(self, tasks_data: List[Dict]) -> List[Dict]:
        if not SUPABASE_ENABLED: return tasks_data
        try:
            print(f"[DB INFO] Batch creating {len(tasks_data)} tasks")
            return supabase_service.batch_create_tasks(tasks_data)
        except Exception as e:
            print(f"[DB ERROR] batch_create_tasks failed: {e}")
            return tasks_data

    def update_task(self, task_id: str, updates: Dict) -> Optional[Dict]:
        if not SUPABASE_ENABLED: return None
        try:
            return supabase_service.update_task(task_id, updates)
        except Exception as e:
            print(f"[DB ERROR] update_task({task_id}) failed: {e}")
            return None

    def delete_task(self, task_id: str) -> bool:
        if not SUPABASE_ENABLED: return False
        try:
            return supabase_service.delete_task(task_id)
        except Exception as e:
            print(f"[DB ERROR] delete_task({task_id}) failed: {e}")
            return False


# ==================== HELPER FUNCTIONS ====================

def get_schedules() -> List[Dict]:
    try:
        if SUPABASE_ENABLED: return supabase_service.get_schedules()
    except Exception as e: print(f"[DB ERROR] get_schedules: {e}")
    return []

def save_schedule(schedule: Dict):
    try:
        if SUPABASE_ENABLED: return supabase_service.save_schedule(schedule)
    except Exception as e: print(f"[DB ERROR] save_schedule: {e}")

def delete_schedule(schedule_id: str):
    try:
        if SUPABASE_ENABLED: return supabase_service.delete_schedule(schedule_id)
    except Exception as e: print(f"[DB ERROR] delete_schedule: {e}")

def get_comments() -> List[Dict]:
    try:
        if SUPABASE_ENABLED: return supabase_service.get_comments()
    except Exception as e: print(f"[DB ERROR] get_comments: {e}")
    return []

def save_comment(comment: Dict):
    try:
        if SUPABASE_ENABLED: return supabase_service.save_comment(comment)
    except Exception as e: print(f"[DB ERROR] save_comment: {e}")

def update_comment(comment_id: str, updates: Dict):
    try:
        if SUPABASE_ENABLED: return supabase_service.update_comment(comment_id, updates)
    except Exception as e: print(f"[DB ERROR] update_comment: {e}")

def delete_comment(comment_id: str):
    try:
        if SUPABASE_ENABLED: return supabase_service.delete_comment(comment_id)
    except Exception as e: print(f"[DB ERROR] delete_comment: {e}")

def get_csms_pb_records() -> List[Dict]:
    try:
        if SUPABASE_ENABLED: return supabase_service.get_csms_pb_records()
    except Exception as e: print(f"[DB ERROR] get_csms_pb: {e}")
    return []

def save_csms_pb(pb: Dict):
    try:
        if SUPABASE_ENABLED: return supabase_service.save_csms_pb(pb)
    except Exception as e: print(f"[DB ERROR] save_csms_pb: {e}")

def update_csms_pb(pb_id: str, updates: Dict):
    try:
        if SUPABASE_ENABLED: return supabase_service.update_csms_pb(pb_id, updates)
    except Exception as e: print(f"[DB ERROR] update_csms_pb: {e}")

def delete_csms_pb(pb_id: str):
    try:
        if SUPABASE_ENABLED: return supabase_service.delete_csms_pb(pb_id)
    except Exception as e: print(f"[DB ERROR] delete_csms_pb: {e}")

def get_related_docs() -> List[Dict]:
    try:
        if SUPABASE_ENABLED: return supabase_service.get_related_docs()
    except Exception as e: print(f"[DB ERROR] get_related_docs: {e}")
    return []

def save_related_doc(doc: Dict):
    try:
        if SUPABASE_ENABLED: return supabase_service.save_related_doc(doc)
    except Exception as e: print(f"[DB ERROR] save_related_doc: {e}")

def delete_related_doc(doc_id: str):
    try:
        if SUPABASE_ENABLED: return supabase_service.delete_related_doc(doc_id)
    except Exception as e: print(f"[DB ERROR] delete_related_doc: {e}")

