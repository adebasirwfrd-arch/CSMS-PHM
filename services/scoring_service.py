import io
import xlsxwriter
from typing import List, Dict

class ScoringService:
    def __init__(self, db):
        self.db = db
        # Criteria mapping based on kriteria scoring.csv
        self.criteria = [
            {"elemen": "ELEMEN 1 – KEPEMIMPINAN DAN KOMITMEN", "items": [
                {"code": "1.1", "factor": 1}
            ]},
            {"elemen": "ELEMEN 2 – TUJUAN KEBIJAKAN HSSE DAN STRATEGI", "items": [
                {"code": "2.1", "factor": 0.5},
                {"code": "2.2", "factor": 0.5}
            ]},
            {"elemen": "ELEMEN 3 – ORGANISASI, TANGGUNG JAWAB, SUMBER DAYA, STANDAR DAN DOKUMENTASI", "items": [
                {"code": "3.1", "factor": 1/6},
                {"code": "3.2", "factor": 1/6},
                {"code": "3.3", "factor": 1/6},
                {"code": "3.4", "factor": 1/6},
                {"code": "3.5", "factor": 1/6},
                {"code": "3.6", "factor": 1/6}
            ]},
            {"elemen": "ELEMEN 4 – MANAJEMEN RISIKO", "items": [
                {"code": "4.1", "factor": 1/8},
                {"code": "4.2", "factor": 1/8},
                {"code": "4.3", "factor": 1/8},
                {"code": "4.4", "factor": 1/8},
                {"code": "4.5", "factor": 1/8},
                {"code": "4.6", "factor": 1/8},
                {"code": "4.7", "factor": 1/8},
                {"code": "4.8", "factor": 1/8}
            ]},
            {"elemen": "ELEMEN 5 – PERENCANAAN DAN PROSEDUR", "items": [
                {"code": "5.1", "factor": 0.25},
                {"code": "5.2", "factor": 0.25},
                {"code": "5.3", "factor": 0.25},
                {"code": "5.4", "factor": 0.25}
            ]},
            {"elemen": "ELEMEN 6 – IMPLEMENTASI DAN PEMANTAUAN KINERJA", "items": [
                {"code": "6.1", "factor": 0.2},
                {"code": "6.2", "factor": 0.2},
                {"code": "6.3", "factor": 0.2},
                {"code": "6.4", "factor": 0.2},
                {"code": "6.5", "factor": 0.2}
            ]},
            {"elemen": "ELEMEN 7 AUDIT DAN TINJAUAN", "items": [
                {"code": "7.1", "factor": 0.5},
                {"code": "7.2", "factor": 0.5}
            ]},
            {"elemen": "ELEMEN 8 – MANAJEMEN K3LL – PENCAPAIAN LAINNYA", "items": [
                {"code": "8.1", "factor": 0.5},
                {"code": "8.2", "factor": 0.5}
            ]}
        ]

    def generate_excel_report(self, project: Dict, tasks: List[Dict]) -> io.BytesIO:
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Scoring')
        
        # Formats
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        elemen_fmt = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0', 'border': 1})
        subtotal_fmt = workbook.add_format({'bold': True, 'border': 1})
        item_fmt = workbook.add_format({'border': 1})
        score_fmt = workbook.add_format({'border': 1, 'align': 'center'})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#C41E3A', 'font_color': 'white', 'border': 1})
        
        # Column definitions
        worksheet.set_column('A:A', 50)
        worksheet.set_column('B:E', 10)
        worksheet.set_column('F:H', 15)

        # Helper to write a row
        current_row = 0
        def write_row(data, format=None):
            nonlocal current_row
            for col, value in enumerate(data):
                worksheet.write(current_row, col, value, format)
            current_row += 1

        # Header Metadata
        write_row(["PROJECT SCORING REPORT", "", "", "", "", "", "", ""])
        write_row(["Project Name:", project.get('name', ''), "", "", "", "", "", ""])
        write_row(["Well Name:", project.get('well_name', project.get('well', '')), "", "", "", "", "", ""])
        write_row(["Contract No:", project.get('kontrak_no', ''), "", "", "", "", "", ""])
        write_row(["", "", "", "", "", "", "", ""])
        
        # Columns Header
        headers = ["Item / Category", "A (0)", "B (3)", "C (6)", "D (10)", "Subtotal", "Factor", "Total"]
        for col, h in enumerate(headers):
            worksheet.write(current_row, col, h, header_fmt)
        current_row += 1
        
        total_rating = 0
        
        for elemen in self.criteria:
            # Elemen Header
            worksheet.write(current_row, 0, elemen["elemen"], elemen_fmt)
            for c in range(1, 8):
                worksheet.write(current_row, c, "", elemen_fmt)
            current_row += 1
            
            elemen_subtotal = 0
            for item in elemen["items"]:
                # Find task by code
                task = next((t for t in tasks if str(t.get('code', '')).strip() == item["code"]), None)
                score = task.get('score', 0) if task else 0
                
                # Mapping score to A, B, C, D
                a, b, c, d = "", "", "", ""
                if score == 0: a = 1
                elif score == 3: b = 1
                elif score == 6: c = 1
                elif score == 10: d = 1
                
                # Write Item Row
                # Item Label
                worksheet.write(current_row, 0, f"{item['code']} {task.get('title', '') if task else ''}", item_fmt)
                # Score Markers
                worksheet.write(current_row, 1, a, score_fmt)
                worksheet.write(current_row, 2, b, score_fmt)
                worksheet.write(current_row, 3, c, score_fmt)
                worksheet.write(current_row, 4, d, score_fmt)
                # Calcs
                worksheet.write(current_row, 5, score, item_fmt)
                worksheet.write(current_row, 6, round(item["factor"], 3), item_fmt)
                worksheet.write(current_row, 7, round(score * item["factor"], 2), item_fmt)
                
                elemen_subtotal += score * item["factor"]
                current_row += 1
            
            # Subtotal Row
            worksheet.write(current_row, 0, f"SUBTOTAL {elemen['elemen'].split('–')[0].strip()}", subtotal_fmt)
            for c in range(1, 7):
                worksheet.write(current_row, c, "", subtotal_fmt)
            worksheet.write(current_row, 7, round(elemen_subtotal, 2), subtotal_fmt)
            
            total_rating += elemen_subtotal
            current_row += 1
            
            # Spacer
            write_row(["", "", "", "", "", "", "", ""])

        # Grand Total
        worksheet.write(current_row, 0, "TOTAL RATING (ELEMEN 1 – ELEMEN 8)", total_fmt)
        for c in range(1, 7):
            worksheet.write(current_row, c, "", total_fmt)
        worksheet.write(current_row, 7, round(total_rating, 2), total_fmt)
        
        workbook.close()
        output.seek(0)
        return output
