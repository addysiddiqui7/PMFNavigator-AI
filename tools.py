import os
import re
import zipfile
import xml.etree.ElementTree as ET
import pandas as pd
import pypdf

class DocumentIngestionTool:
    """
    Ingests and parses multiple document formats (CSV, XLSX, PDF, DOCX) 
    from a file or folder, returning unified text documents.
    """
    def __init__(self):
        self.sources_count = 0
        self.types_present = set()

    def _parse_csv(self, file_path: str) -> str:
        try:
            df = pd.read_csv(file_path)
            columns = list(df.columns)
            feedback_cols = [
                col for col in columns 
                if any(x in col.lower() for x in ["review", "feedback", "text", "comment", "body", "opinion", "message"])
            ]
            
            rows_text = []
            for idx, row in df.iterrows():
                row_parts = []
                if feedback_cols:
                    for col in feedback_cols:
                        if pd.notna(row[col]):
                            row_parts.append(f"{col}: {row[col]}")
                else:
                    for col in columns:
                        if pd.notna(row[col]):
                            row_parts.append(f"{col}: {row[col]}")
                if row_parts:
                    rows_text.append(f"Row {idx+1}: " + " | ".join(row_parts))
            
            return f"### CSV Source: {os.path.basename(file_path)}\n" + "\n".join(rows_text)
        except Exception as e:
            return f"Error parsing CSV '{os.path.basename(file_path)}': {e}"

    def _parse_xlsx(self, file_path: str) -> str:
        try:
            excel_file = pd.ExcelFile(file_path)
            sheets_text = [f"### Excel Source: {os.path.basename(file_path)}"]
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                sheets_text.append(f"Sheet: {sheet_name}")
                sheets_text.append(df.to_string(index=False))
            return "\n".join(sheets_text)
        except Exception as e:
            return f"Error parsing Excel '{os.path.basename(file_path)}': {e}"

    def _parse_docx(self, file_path: str) -> str:
        try:
            with zipfile.ZipFile(file_path) as docx:
                xml_content = docx.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                texts = [node.text for node in tree.findall('.//w:t', namespaces) if node.text]
                return f"### Word Document Source: {os.path.basename(file_path)}\n" + "\n".join(texts)
        except Exception as e:
            return f"Error parsing Word DOCX '{os.path.basename(file_path)}': {e}"

    def _parse_pdf(self, file_path: str) -> str:
        try:
            text_content = [f"### PDF Source: {os.path.basename(file_path)}"]
            reader = pypdf.PdfReader(file_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
            return "\n".join(text_content)
        except Exception as e:
            return f"Error parsing PDF '{os.path.basename(file_path)}': {e}"

    def run(self, path: str) -> str:
        if not path or path.lower() == 'none' or not os.path.exists(path):
            return ""

        files_to_process = []
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in ['.csv', '.xlsx', '.pdf', '.docx']:
                        files_to_process.append(os.path.join(root, file))
        else:
            ext = os.path.splitext(path)[1].lower()
            if ext in ['.csv', '.xlsx', '.pdf', '.docx']:
                files_to_process.append(path)

        if not files_to_process:
            return ""

        self.sources_count = 0
        self.types_present = set()
        unified_docs = []

        for file_path in files_to_process:
            filename = os.path.basename(file_path)
            ext = os.path.splitext(filename)[1].lower()
            
            text = ""
            file_type = ""
            if ext == '.csv':
                text = self._parse_csv(file_path)
                file_type = "csv"
            elif ext == '.xlsx':
                text = self._parse_xlsx(file_path)
                file_type = "xlsx"
            elif ext == '.docx':
                text = self._parse_docx(file_path)
                file_type = "docx"
            elif ext == '.pdf':
                text = self._parse_pdf(file_path)
                file_type = "pdf"
                
            if text and not text.startswith("Error"):
                unified_docs.append(text)
                self.types_present.add(file_type)
                self.sources_count += 1
                
        return "\n\n" + "="*40 + "\n\n".join(unified_docs)

    def get_metadata_summary(self) -> dict:
        return {
            "sources_count": self.sources_count,
            "types_present": list(self.types_present)
        }

class CSVReaderTool(DocumentIngestionTool):
    """
    Backward-compatible wrapper to maintain continuity for agents expecting CSVReaderTool.
    """
    pass
