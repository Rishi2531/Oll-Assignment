import pdfplumber
from pdf2image import convert_from_path
import pytesseract
from pathlib import Path
import tempfile
import os

from .utils import run_cmd_or_raise

API_KEY = os.getenv("APILAYER_API_KEY")
API_URL = "https://api.apilayer.com/resume_parser/upload"

def extract_textpdf(pdf_path:Path):
    text=""
    used_ocr = False
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text+=page_text+"\n"
    if len(text.strip())<80:
        used_ocr=True

        images = convert_from_path(str(pdf_path))
        ocr_text=""
        for i in images:
            ocr_text+=pytesseract.imgage_to_string(i)+"\n"
        text=ocr_text
    return text,used_ocr

def getats_score(pdf_path:str):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"{pdf_path} does not exist")
    with open(pdf_path,"rb") as f:
        file = {"file":f}
        headers = {"apikey":API_KEY}
        response = requests.post(API_URL,headers=headers,files=files)
    if response.status_code!=200:
        raise Exception(f"Api request failed:{response.status_code}{response.text}")
    data=response.json()

    sections=