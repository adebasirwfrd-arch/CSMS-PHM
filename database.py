"""
RELIABLE Database Layer - Supabase is the SINGLE SOURCE OF TRUTH
- ALL reads go to Supabase (when enabled)
- ALL writes go to Supabase SYNCHRONOUSLY (will fail loudly if it fails)
- Local JSON is ONLY a fallback when Supabase is not configured
"""
import json
import os
from typing import List, Dict, Optional
import uuid
from datetime import datetime

# Try to import Supabase service
try:
    from services.supabase_service import supabase_service
    SUPABASE_ENABLED = supabase_service.enabled if supabase_service else False
except ImportError:
    supabase_service = None
    SUPABASE_ENABLED = False

print(f"[DB] ========================================")
print(f"[DB] Supabase enabled: {SUPABASE_ENABLED}")
if SUPABASE_ENABLED:
    print(f"[DB] MODE: Supabase is SINGLE SOURCE OF TRUTH")
    print(f"[DB] All reads/writes go directly to Supabase")
else:
    print(f"[DB] MODE: Local JSON fallback (Supabase not configured)")
print(f"[DB] ========================================")

# Local JSON storage paths (fallback only)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
SCHEDULES_FILE = os.path.join(DATA_DIR, "schedules.json")
COMMENTS_FILE = os.path.join(DATA_DIR, "comments.json")
CSMS_PB_FILE = os.path.join(DATA_DIR, "csms_pb.json")
RELATED_DOCS_FILE = os.path.join(DATA_DIR, "related_docs.json")


class Database:
    """
    RELIABLE Database - Supabase as single source of truth
    - When Supabase enabled: ALL operations go to Supabase SYNCHRONOUSLY
    - When Supabase disabled: Falls back to local JSON
    """
    
    def __init__(self):
        # Only create local files if Supabase is NOT enabled
        # Vercel has read-only filesystem, so we skip this when using Supabase
        if not SUPABASE_ENABLED:
            try:
                os.makedirs(DATA_DIR, exist_ok=True)
                self._ensure_file(PROJECTS_FILE)
                self._ensure_file(TASKS_FILE)
            except OSError as e:
                print(f"[DB] Warning: Could not create local data files: {e}")
                print("[DB] This is expected on read-only filesystems (e.g., Vercel)")

    def _ensure_file(self, filepath):
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                json.dump([], f)

    def _read_json(self, filepath) -> List[Dict]:
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_json(self, filepath, data: List[Dict]):
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    # ==================== PROJECTS ====================
    
    def get_projects(self) -> List[Dict]:
        """Get all projects from Supabase (or local fallback)"""
        if SUPABASE_ENABLED:
            return supabase_service.get_projects()
        return self._read_json(PROJECTS_FILE)

    def get_project(self, project_id: str) -> Optional[Dict]:
        """Get single project by ID"""
        if SUPABASE_ENABLED:
            return supabase_service.get_project(project_id)
        projects = self.get_projects()
        return next((p for p in projects if p['id'] == project_id), None)

    def create_project(self, project_data: Dict) -> Dict:
        """Create project - SYNCHRONOUS write to Supabase"""
        new_project = {
            "id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            **project_data
        }
        
        if SUPABASE_ENABLED:
            # SYNCHRONOUS - will raise exception if fails
            result = supabase_service.create_project(new_project)
            print(f"[DB] Project created in Supabase: {result.get('id')}")
            return result
        else:
            # Local fallback
            projects = self.get_projects()
            projects.append(new_project)
            self._write_json(PROJECTS_FILE, projects)
            return new_project

    def update_project(self, project_id: str, updates: Dict) -> Optional[Dict]:
        """Update project - SYNCHRONOUS write to Supabase"""
        if SUPABASE_ENABLED:
            # SYNCHRONOUS - will raise exception if fails
            result = supabase_service.update_project(project_id, updates)
            print(f"[DB] Project updated in Supabase: {project_id}")
            return result
        else:
            projects = self.get_projects()
            for i, p in enumerate(projects):
                if p['id'] == project_id:
                    projects[i] = {**p, **updates}
                    self._write_json(PROJECTS_FILE, projects)
                    return projects[i]
            return None

    def delete_project(self, project_id: str) -> bool:
        """Delete project - SYNCHRONOUS write to Supabase"""
        if SUPABASE_ENABLED:
            # SYNCHRONOUS - will raise exception if fails
            result = supabase_service.delete_project(project_id)
            print(f"[DB] Project deleted from Supabase: {project_id}")
            return result
        else:
            projects = [p for p in self.get_projects() if p['id'] != project_id]
            self._write_json(PROJECTS_FILE, projects)
            return True

    # ==================== TASKS ====================
    
    def get_tasks(self, project_id: str = None) -> List[Dict]:
        """Get all tasks from Supabase (or local fallback)"""
        if SUPABASE_ENABLED:
            return supabase_service.get_tasks(project_id)
        tasks = self._read_json(TASKS_FILE)
        return [t for t in tasks if t.get('project_id') == project_id] if project_id else tasks

    def create_task(self, task_data: Dict) -> Dict:
        """Create task - SYNCHRONOUS write to Supabase"""
        new_task = {
            "id": str(uuid.uuid4()),
            "status": "Upcoming",
            "created_at": datetime.now().isoformat(),
            "attachments": [],
            **task_data
        }
        
        if SUPABASE_ENABLED:
            # SYNCHRONOUS - will raise exception if fails
            result = supabase_service.create_task(new_task)
            print(f"[DB] Task created in Supabase: {result.get('id')}")
            return result
        else:
            tasks = self.get_tasks()
            tasks.append(new_task)
            self._write_json(TASKS_FILE, tasks)
            return new_task
    
    def batch_create_tasks(self, tasks_data: List[Dict]) -> List[Dict]:
        """Create multiple tasks - SYNCHRONOUS batch write to Supabase"""
        new_tasks = [
            {
                "id": str(uuid.uuid4()),
                "status": "Upcoming",
                "created_at": datetime.now().isoformat(),
                "attachments": [],
                **t
            } 
            for t in tasks_data
        ]
        
        if SUPABASE_ENABLED:
            # SYNCHRONOUS batch insert - will raise exception if fails
            result = supabase_service.batch_create_tasks(new_tasks)
            print(f"[DB] {len(result)} tasks created in Supabase (batch)")
            return result
        else:
            tasks = self.get_tasks()
            tasks.extend(new_tasks)
            self._write_json(TASKS_FILE, tasks)
            return new_tasks

    def update_task(self, task_id: str, updates: Dict) -> Optional[Dict]:
        """Update task - SYNCHRONOUS write to Supabase"""
        if SUPABASE_ENABLED:
            # SYNCHRONOUS - will raise exception if fails
            result = supabase_service.update_task(task_id, updates)
            print(f"[DB] Task updated in Supabase: {task_id}")
            return result
        else:
            tasks = self.get_tasks()
            for i, t in enumerate(tasks):
                if t['id'] == task_id:
                    tasks[i] = {**t, **updates}
                    self._write_json(TASKS_FILE, tasks)
                    return tasks[i]
            return None

    def delete_task(self, task_id: str) -> bool:
        """Delete task - SYNCHRONOUS write to Supabase"""
        if SUPABASE_ENABLED:
            # SYNCHRONOUS - will raise exception if fails
            result = supabase_service.delete_task(task_id)
            print(f"[DB] Task deleted from Supabase: {task_id}")
            return result
        else:
            tasks = [t for t in self.get_tasks() if t['id'] != task_id]
            self._write_json(TASKS_FILE, tasks)
            return True


# ==================== HELPER FUNCTIONS (for other data types) ====================
# These also use Supabase when enabled

def get_schedules() -> List[Dict]:
    if SUPABASE_ENABLED:
        return supabase_service.get_schedules()
    return json.load(open(SCHEDULES_FILE)) if os.path.exists(SCHEDULES_FILE) else []

def save_schedule(schedule: Dict):
    """Save single schedule - SYNCHRONOUS"""
    if SUPABASE_ENABLED:
        return supabase_service.save_schedule(schedule)
    schedules = get_schedules()
    schedules.append(schedule)
    with open(SCHEDULES_FILE, 'w') as f:
        json.dump(schedules, f, indent=2)

def delete_schedule(schedule_id: str):
    """Delete schedule - SYNCHRONOUS"""
    if SUPABASE_ENABLED:
        return supabase_service.delete_schedule(schedule_id)
    schedules = [s for s in get_schedules() if s.get('id') != schedule_id]
    with open(SCHEDULES_FILE, 'w') as f:
        json.dump(schedules, f, indent=2)

def save_schedules(schedules: List[Dict]):
    with open(SCHEDULES_FILE, 'w') as f:
        json.dump(schedules, f, indent=2)

def get_comments() -> List[Dict]:
    if SUPABASE_ENABLED:
        return supabase_service.get_comments()
    return json.load(open(COMMENTS_FILE)) if os.path.exists(COMMENTS_FILE) else []

def save_comment(comment: Dict):
    """Save single comment - SYNCHRONOUS"""
    if SUPABASE_ENABLED:
        return supabase_service.save_comment(comment)
    comments = get_comments()
    comments.append(comment)
    with open(COMMENTS_FILE, 'w') as f:
        json.dump(comments, f, indent=2)

def update_comment(comment_id: str, updates: Dict):
    """Update comment - SYNCHRONOUS"""
    if SUPABASE_ENABLED:
        return supabase_service.update_comment(comment_id, updates)
    comments = get_comments()
    for c in comments:
        if c.get('id') == comment_id:
            c.update(updates)
    with open(COMMENTS_FILE, 'w') as f:
        json.dump(comments, f, indent=2)

def delete_comment(comment_id: str):
    """Delete comment - SYNCHRONOUS"""
    if SUPABASE_ENABLED:
        return supabase_service.delete_comment(comment_id)
    comments = [c for c in get_comments() if c.get('id') != comment_id]
    with open(COMMENTS_FILE, 'w') as f:
        json.dump(comments, f, indent=2)

def save_comments(comments: List[Dict]):
    with open(COMMENTS_FILE, 'w') as f:
        json.dump(comments, f, indent=2)

def get_csms_pb_records() -> List[Dict]:
    if SUPABASE_ENABLED:
        return supabase_service.get_csms_pb_records()
    return json.load(open(CSMS_PB_FILE)) if os.path.exists(CSMS_PB_FILE) else []

def save_csms_pb(pb: Dict):
    """Save single CSMS PB - SYNCHRONOUS"""
    if SUPABASE_ENABLED:
        return supabase_service.save_csms_pb(pb)
    records = get_csms_pb_records()
    records.append(pb)
    with open(CSMS_PB_FILE, 'w') as f:
        json.dump(records, f, indent=2)

def update_csms_pb(pb_id: str, updates: Dict):
    """Update CSMS PB - SYNCHRONOUS"""
    if SUPABASE_ENABLED:
        return supabase_service.update_csms_pb(pb_id, updates)
    records = get_csms_pb_records()
    for r in records:
        if r.get('id') == pb_id:
            r.update(updates)
    with open(CSMS_PB_FILE, 'w') as f:
        json.dump(records, f, indent=2)

def delete_csms_pb(pb_id: str):
    """Delete CSMS PB - SYNCHRONOUS"""
    if SUPABASE_ENABLED:
        return supabase_service.delete_csms_pb(pb_id)
    records = [r for r in get_csms_pb_records() if r.get('id') != pb_id]
    with open(CSMS_PB_FILE, 'w') as f:
        json.dump(records, f, indent=2)

def save_csms_pb_records(records: List[Dict]):
    with open(CSMS_PB_FILE, 'w') as f:
        json.dump(records, f, indent=2)

def get_related_docs() -> List[Dict]:
    if SUPABASE_ENABLED:
        return supabase_service.get_related_docs()
    return json.load(open(RELATED_DOCS_FILE)) if os.path.exists(RELATED_DOCS_FILE) else []

def save_related_doc(doc: Dict):
    """Save single related doc - SYNCHRONOUS"""
    if SUPABASE_ENABLED:
        return supabase_service.save_related_doc(doc)
    docs = get_related_docs()
    docs.append(doc)
    with open(RELATED_DOCS_FILE, 'w') as f:
        json.dump(docs, f, indent=2)

def delete_related_doc(doc_id: str):
    """Delete related doc - SYNCHRONOUS"""
    if SUPABASE_ENABLED:
        return supabase_service.delete_related_doc(doc_id)
    docs = [d for d in get_related_docs() if d.get('id') != doc_id]
    with open(RELATED_DOCS_FILE, 'w') as f:
        json.dump(docs, f, indent=2)

def save_related_docs(docs: List[Dict]):
    with open(RELATED_DOCS_FILE, 'w') as f:
        json.dump(docs, f, indent=2)


