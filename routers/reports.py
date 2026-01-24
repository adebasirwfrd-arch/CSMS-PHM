from fastapi import APIRouter, UploadFile, File, HTTPException, Response
from services.report_engine import ReportEngine
from typing import List, Optional

router = APIRouter(prefix="/api/reports", tags=["reports"])
report_engine = ReportEngine()

@router.post("/generate")
async def generate_report(
    template_file: Optional[UploadFile] = File(None),
    source_files: List[UploadFile] = File(...),
    force_csv: Optional[str] = None,
):
    """
    Generate a report by filling a template with data from MULTIPLE source files.
    If force_csv is 'true', output will be CSV regardless of template.
    """
    try:
        # Read Template (if provided)
        if template_file:
            template_content = await template_file.read()
            template_filename = template_file.filename
        else:
            # Dummy CSV template if not provided
            template_content = b""
            template_filename = "report.csv"

        # Force CSV output if requested
        print(f"[DEBUG] force_csv received: '{force_csv}'")
        if force_csv == 'true':
            template_filename = "report.csv"  # Override to trigger CSV logic
            print(f"[DEBUG] Forcing CSV output. template_filename = {template_filename}")

        # Read Sources
        source_contents = []
        source_filenames = []
        for sf in source_files:
            content = await sf.read()
            source_contents.append(content)
            source_filenames.append(sf.filename)
        
        # Process
        result = report_engine.process_request(
            template_content=template_content,
            template_filename=template_filename,
            source_contents=source_contents,
            source_filenames=source_filenames
        )
        
        if not result:
            raise HTTPException(status_code=400, detail="Failed to generate report. Check input files.")
            
        # Determine media type based on output
        media_type = "application/octet-stream"
        output_filename = f"generated_{template_filename}"
        
        if template_filename.endswith('.docx'):
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif template_filename.endswith('.xlsx'):
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif template_filename.endswith('.csv'):
            media_type = "text/csv"
            output_filename = "generated_report.csv"
            
        return Response(
            content=result,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )
        
    except Exception as e:
        print(f"[API ERROR] Report generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/preview")
async def preview_source_data(
    source_file: UploadFile = File(...)
):
    """
    Preview the data extracted from the source file.
    """
    try:
        source_content = await source_file.read()
        
        data = []
        if source_file.filename.lower().endswith('.xlsx') or source_file.filename.lower().endswith('.xls'):
            data = report_engine.parse_excel_source(source_content)
        elif source_file.filename.lower().endswith('.pdf'):
            data = report_engine.parse_pdf_source(source_content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported source file type")
            
        return {
            "filename": source_file.filename,
            "record_count": len(data),
            "preview": data[:5] # Show first 5 records
        }
        
    except Exception as e:
        print(f"[API ERROR] Preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
