import io
import pandas as pd
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
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        workbook = writer.book
        
        # Formats
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        elemen_fmt = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0', 'border': 1})
        subtotal_fmt = workbook.add_format({'bold': True, 'border': 1})
        item_fmt = workbook.add_format({'border': 1})
        score_fmt = workbook.add_format({'border': 1, 'align': 'center'})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#C41E3A', 'font_color': 'white', 'border': 1})

        rows = []
        # Header Metadata
        rows.append(["PROJECT SCORING REPORT", "", "", "", "", "", "", ""])
        rows.append(["Project Name:", project.get('name', ''), "", "", "", "", "", ""])
        rows.append(["Well Name:", project.get('well_name', project.get('well', '')), "", "", "", "", "", ""])
        rows.append(["Contract No:", project.get('kontrak_no', ''), "", "", "", "", "", ""])
        rows.append(["", "", "", "", "", "", "", ""])
        
        # Columns
        rows.append(["Item / Category", "A (0)", "B (3)", "C (6)", "D (10)", "Subtotal", "Factor", "Total"])
        
        total_rating = 0
        
        for elemen in self.criteria:
            rows.append([elemen["elemen"], "", "", "", "", "", "", ""])
            
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
                
                rows.append([
                    f"{item['code']} {task.get('title', '') if task else ''}",
                    a, b, c, d,
                    score,
                    round(item["factor"], 3),
                    round(score * item["factor"], 2)
                ])
                elemen_subtotal += score * item["factor"]
            
            rows.append([f"SUBTOTAL {elemen['elemen'].split('–')[0].strip()}", "", "", "", "", "", "", round(elemen_subtotal, 2)])
            total_rating += elemen_subtotal
            rows.append(["", "", "", "", "", "", "", ""])

        rows.append(["TOTAL RATING (ELEMEN 1 – ELEMEN 8)", "", "", "", "", "", "", round(total_rating, 2)])
        
        # Create DataFrame
        df = pd.DataFrame(rows)
        df.to_excel(writer, index=False, header=False, sheet_name='Scoring')
        
        # Adjust columns
        worksheet = writer.sheets['Scoring']
        worksheet.set_column('A:A', 50)
        worksheet.set_column('B:E', 10)
        worksheet.set_column('F:H', 15)
        
        writer.close()
        output.seek(0)
        return output
