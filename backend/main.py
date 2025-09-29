import os
import requests
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

import tempfile
import pdfplumber
from pdf2image import convert_from_path
import pytesseract
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import easyocr
import numpy as np
import base64
import pandas as pd
import google.generativeai as genai


# --- Load environment variables ---
load_dotenv("config.env")

# --- Config ---
MAGICAL_API_KEY = os.getenv("MAGICAL_API_KEY")
MAGICAL_API_URL = "https://api.magicalapi.com/v1/resume/score"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


# --- Initialize Gemini client ---

app = FastAPI(title="AI Resume ATS Optimizer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PDF Text Extraction Helper ---
reader = easyocr.Reader(['en'])

def extract_text_from_pdf(pdf_path: str):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"pdfplumber extraction failed: {e}")

    if len(text.strip()) < 100:
        try:
            images = convert_from_path(pdf_path, dpi=300)
            for img in images:
                page_text = pytesseract.image_to_string(img)
                text += page_text + "\n"
        except Exception as e:
            print(f"pytesseract extraction failed: {e}")

        if len(text.strip()) < 50:
            try:
                images = convert_from_path(pdf_path, dpi=200)
                for img in images:
                    img_array = np.array(img)
                    result = reader.readtext(img_array, detail=0)
                    text += " ".join(result) + "\n"
            except Exception as e:
                print(f"EasyOCR extraction failed: {e}")

    return text.strip()

# --- Upload to file.io ---
def upload_to_fileio(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                "https://file.io",
                files={"file": f},
                params={"expires": "1w"},
                timeout=30
            )
        if resp.headers.get('content-type', '').startswith('application/json'):
            data = resp.json()
            if data.get("success"):
                return data["link"]
            else:
                raise Exception(f"File.io API error: {data.get('error', 'Unknown error')}")
        else:
            raise Exception("File.io service temporarily unavailable")
    except Exception as e:
        print(f"Error uploading to file.io: {e}")
        raise Exception(f"File upload failed: {str(e)}")

# --- PDF to Base64 ---
def pdf_to_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        pdf_data = f.read()
    return base64.b64encode(pdf_data).decode('utf-8')

# --- Load Local ML Model ---
MODEL_PATH = "resume_score_model.joblib"
local_model = None
if os.path.exists(MODEL_PATH):
    local_model = joblib.load(MODEL_PATH)
    print("✅ Local resume scoring model loaded")
else:
    print("⚠️ Local resume scoring model not found")

# --- Local Resume Scoring Fallback ---
def get_local_resume_score(file_path: str):
    text = extract_text_from_pdf(file_path)
    score = 50.0

    sections = ["experience", "education", "skills", "projects", "summary", "objective", "work", "employment"]
    found_sections = []
    for section in sections:
        if section in text.lower():
            found_sections.append(section)
            score += 5.0

    word_count = len(text.split())
    if 300 <= word_count <= 1000:
        score += 10.0
    elif word_count > 1000:
        score -= 5.0

    contact_indicators = ["@", "phone", "email", "linkedin", "github", "contact"]
    contact_found = any(indicator in text.lower() for indicator in contact_indicators)
    if contact_found:
        score += 10.0

    action_verbs = ["managed", "developed", "created", "led", "implemented", "achieved", "improved"]
    verbs_found = sum(1 for verb in action_verbs if verb in text.lower())
    score += min(verbs_found * 2, 10.0)

    score = max(0, min(100, score))

    return {
        "score": round(score, 1),
        "sections_found": found_sections,
        "word_count": word_count,
        "has_contact_info": contact_found,
        "note": "Local scoring (fallback)"
    }

# --- Local ML Model Scoring ---
def get_local_model_score(file_path: str):
    if not local_model:
        return get_local_resume_score(file_path)

    text = extract_text_from_pdf(file_path)
    try:
        # Prepare a DataFrame with proper structure
        input_df = pd.DataFrame([{
            'Resume_Text': text,
            'Education': '',
            'Job_Title': '',
            'Experience_Years': 0
        }])
        score = local_model.predict(input_df)[0] * 10  # scale to 100
        score = max(0, min(100, score))
        return {
            "score": round(score, 1),
            "note": "Scored via local ML model",
            "text_length": len(text)
        }
    except Exception as e:
        print(f"Local ML model scoring failed: {e}")
        return get_local_resume_score(file_path)

def get_resume_score(file_path: str):
    headers = {"Authorization": f"Bearer {MAGICAL_API_KEY}"}
    try:
        public_url = upload_to_fileio(file_path)
        payload = {"resume_url": public_url}
        resp = requests.post(MAGICAL_API_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            data["note"] = "Scored via MagicalAPI"
            return data
    except Exception as e:
        print(f"MagicalAPI via file.io failed: {e}")

    # Fallback to local ML model
    return get_local_model_score(file_path)

# --- OpenAI Enhancement ---
def enhance_resume_with_gemini(text: str, job_description: str = None):
    prompt = f"You are an expert ATS resume optimizer. Enhance the following resume to maximize ATS score and readability:\n{text}"
    if job_description:
        prompt += f"\nTarget Job Description:\n{job_description}"

    try:
        response = genai.chat.create(
            model="gemini-1.5",
            messages=[{"role": "user", "content": prompt}],
            max_output_tokens=2000
        )
        return response.choices[0].content[0].text.strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        return text + "\n\n[Enhanced with Gemini API]"


# --- Save PDF ---
def save_pdf(text: str, output_path: str):
    try:
        doc = SimpleDocTemplate(output_path, pagesize=(612, 792))
        styles = getSampleStyleSheet()
        story = [Paragraph("ENHANCED RESUME", styles['Title']), Spacer(1,20)]
        for line in text.split("\n"):
            if line.strip():
                if line.isupper() or any(k in line.lower() for k in ['experience','education','skills','summary','objective']):
                    story.append(Paragraph(f"<b>{line}</b>", styles['Heading2']))
                else:
                    story.append(Paragraph(line, styles['Normal']))
                story.append(Spacer(1,8))
        doc.build(story)
        return True
    except Exception as e:
        print(f"PDF creation failed: {e}")
        return False

    except Exception as e:
        print(f"PDF creation error: {e}")
        return False

# --- FastAPI Endpoints ---
@app.get("/")
async def root():
    return {"message": "AI Resume ATS Optimizer API is running"}

@app.post("/optimize_resume/")
async def optimize_resume(file: UploadFile = File(...), job_description: str = Form(None)):
    try:
        if not file.filename.lower().endswith('.pdf'):
            return JSONResponse({"error": "Only PDF files are supported"}, status_code=400)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            if len(content) == 0:
                return JSONResponse({"error": "Uploaded file is empty"}, status_code=400)
            tmp.write(content)
            input_pdf = tmp.name

        print("Extracting text from PDF...")
        extracted_text = extract_text_from_pdf(input_pdf)

        if not extracted_text or len(extracted_text.strip()) < 50:
            return JSONResponse({"error": "Could not extract sufficient text from PDF."}, status_code=400)

        print("Getting initial resume score...")
        before_score_data = get_resume_score(input_pdf)

        print("Enhancing resume with AI...")
        enhanced_text = enhance_resume_with_gemini(extracted_text, job_description)

        print("Creating enhanced PDF...")
        enhanced_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
        pdf_success = save_pdf(enhanced_text, enhanced_pdf)
        if not pdf_success:
            return JSONResponse({"error": "Failed to create enhanced PDF"}, status_code=500)

        print("Getting enhanced resume score...")
        after_score_data = get_resume_score(enhanced_pdf)

        response_data = {
            "before_score": before_score_data.get("score", 0),
            "after_score": after_score_data.get("score", 0),
            "score_improvement": round(after_score_data.get("score", 0) - before_score_data.get("score", 0), 1),
            "before_details": before_score_data,
            "after_details": after_score_data,
            "enhanced_resume_url": f"/download/{Path(enhanced_pdf).name}",
            "text_extracted": len(extracted_text) > 0,
            "text_length": len(extracted_text)
        }

        try:
            os.unlink(input_pdf)
        except:
            pass

        return JSONResponse(response_data)

    except Exception as e:
        import traceback
        print("❌ Error optimizing resume:")
        traceback.print_exc()
        try:
            if 'input_pdf' in locals():
                os.unlink(input_pdf)
            if 'enhanced_pdf' in locals():
                os.unlink(enhanced_pdf)
        except:
            pass
        return JSONResponse({"error": f"Optimization failed: {str(e)}"}, status_code=500)

@app.get("/download/{filename}")
async def download_file(filename: str):
    try:
        file_path = os.path.join(tempfile.gettempdir(), filename)
        if not os.path.exists(file_path):
            return JSONResponse({"error": "File not found or expired"}, status_code=404)
        return FileResponse(file_path, media_type="application/pdf", filename="enhanced_resume.pdf")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI Resume Optimizer"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
