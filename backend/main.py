import os
import requests
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
import tempfile
import pdfplumber
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- API Keys ---
AFFINDA_API_KEY = os.getenv("AFFINDA_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Affinda API configuration
AFFINDA_API_URL = "https://api.affinda.com/v2/resumes"
AFFINDA_HEADERS = {"Authorization": f"Bearer {AFFINDA_API_KEY}"}

app = FastAPI(title="AI Resume ATS Optimizer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PDF Text Extraction ---
def extract_text_from_pdf(pdf_path: str):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"PDF extraction failed: {e}")
    return text.strip()

# --- Affinda API Resume Parsing ---
def parse_resume_with_affinda(file_path: str):
    if not AFFINDA_API_KEY:
        return {"error": "Affinda API key not configured"}

    try:
        with open(file_path, "rb") as file:
            files = {"file": (Path(file_path).name, file, "application/pdf")}
            response = requests.post(
                AFFINDA_API_URL,
                headers=AFFINDA_HEADERS,
                files=files,
                timeout=60
            )
        if response.status_code == 201:
            return response.json()
        else:
            return {"error": f"Affinda API error {response.status_code}: {response.text}"}
    except Exception as e:
        return {"error": str(e)}

# --- Extract ATS Score ---
def extract_affinda_ats_score(affinda_data: dict):
    if "error" in affinda_data:
        return {"score": 0, "note": "Affinda parsing failed", "details": affinda_data}

    data = affinda_data.get("data", {})

    ats = data.get("ats", {})
    raw_score = ats.get("overallScore")
    score = round(raw_score * 100, 1) if raw_score is not None else calculate_fallback_score(data)

    skills = data.get("skills", [])
    work_experience = data.get("workExperience", [])
    education = data.get("education", [])

    return {
        "score": score,
        "sections_found": [
            s for s in ["education", "experience", "skills", "summary"]
            if data.get(s)
        ],
        "has_contact_info": bool(
            data.get("emails") or data.get("phoneNumbers") or data.get("websites")
        ),
        "skills_analysis": {
            "total_skills": len(skills),
            "top_skills": [s.get("name") for s in skills[:10] if s.get("name")],
            "skills_found": [s.get("name") for s in skills if s.get("name")]
        },
        "experience_analysis": {
            "total_years": data.get("totalYearsExperience", 0),
            "job_count": len(work_experience),
            "recent_positions": [
                {
                    "title": exp.get("jobTitle"),
                    "company": exp.get("organization"),
                    "duration": exp.get("dates", {}).get("rawText")
                }
                for exp in work_experience[:3]
            ]
        },
        "education_analysis": {
            "degree_count": len(education),
            "highest_degree": education[0].get("accreditation", {}).get("education") if education else None,
            "institutions": [edu.get("organization") for edu in education if edu.get("organization")]
        },
        "note": "ATS scoring provided by Affinda API",
        "affinda_ats_breakdown": ats
    }

def calculate_fallback_score(data: dict):
    score = 50.0
    if data.get("education"): score += min(len(data["education"]) * 5, 20)
    if data.get("workExperience"): score += min(len(data["workExperience"]) * 5, 25)
    if data.get("skills"): score += min(len(data["skills"]) * 1.5, 15)
    if data.get("emails") or data.get("phoneNumbers"): score += 10
    return max(0, min(100, round(score, 1)))

# --- AI Enhancement ---
def enhance_resume_with_gemini(affinda_data: dict, ats_score: float, job_description: str = None):
    if not GEMINI_API_KEY:
        return "AI enhancement not available - Gemini API key missing"
    try:
        data = affinda_data.get("data", {})
        resume_info = f"""
        Name: {data.get('name', {}).get('raw', 'Not found')}
        Email: {data.get('emails', ['Not found'])[0] if data.get('emails') else 'Not found'}
        Phone: {data.get('phoneNumbers', ['Not found'])[0] if data.get('phoneNumbers') else 'Not found'}
        Education: {len(data.get('education', []))}
        Experience: {len(data.get('workExperience', []))} roles, {data.get('totalYearsExperience', 0)} years
        Skills: {len(data.get('skills', []))}
        Summary: {data.get('summary', 'Not provided')}
        Current ATS Score: {ats_score}/100
        """
        prompt = f"As an ATS resume optimizer, analyze and improve:\n{resume_info}"
        if job_description:
            prompt += f"\nTarget Job Description:\n{job_description}"
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"AI enhancement failed: {str(e)}"

# --- Save Enhanced Resume ---
def save_enhanced_resume(affinda_data: dict, ats_score: float, recommendations: str, output_path: str):
    try:
        data = affinda_data.get("data", {})
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("AFFINDA RESUME ATS ANALYSIS REPORT\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Name: {data.get('name', {}).get('raw', 'N/A')}\n")
            f.write(f"Email: {data.get('emails', ['N/A'])[0] if data.get('emails') else 'N/A'}\n")
            f.write(f"ATS Score: {ats_score}/100\n")
            f.write(f"Experience: {data.get('totalYearsExperience', 0)} years\n")
            f.write(f"Education: {len(data.get('education', []))}\n")
            f.write(f"Skills: {len(data.get('skills', []))}\n\n")
            f.write("AI RECOMMENDATIONS:\n")
            f.write(recommendations)
        return True
    except Exception as e:
        print(f"File creation failed: {e}")
        return False

# --- Endpoints ---
@app.get("/")
async def root():
    return {"message": "AI Resume ATS Optimizer API with Affinda ATS Scoring"}

@app.post("/analyze_resume/")
async def analyze_resume(file: UploadFile = File(...), job_description: str = Form(None)):
    try:
        if not file.filename.lower().endswith('.pdf'):
            return JSONResponse({"error": "Only PDF files are supported"}, status_code=400)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            if not content:
                return JSONResponse({"error": "Uploaded file is empty"}, status_code=400)
            tmp.write(content)
            input_pdf = tmp.name

        affinda_data = parse_resume_with_affinda(input_pdf)
        score_data = extract_affinda_ats_score(affinda_data)
        recommendations = enhance_resume_with_gemini(affinda_data, score_data["score"], job_description)
        enhanced_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
        save_success = save_enhanced_resume(affinda_data, score_data["score"], recommendations, enhanced_file)

        os.unlink(input_pdf) if os.path.exists(input_pdf) else None

        return JSONResponse({
            "success": True,
            "ats_score": score_data["score"],
            "resume_analysis": score_data,
            "ai_recommendations": recommendations,
            "analysis_report_url": f"/download/{Path(enhanced_file).name}" if save_success else None
        })
    except Exception as e:
        return JSONResponse({"error": f"Analysis failed: {str(e)}"}, status_code=500)

@app.get("/download/{filename}")
async def download_file(filename: str):
    try:
        file_path = os.path.join(tempfile.gettempdir(), filename)
        if not os.path.exists(file_path):
            return JSONResponse({"error": "File not found"}, status_code=404)
        return FileResponse(file_path, media_type="text/plain", filename="resume_ats_analysis.txt")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "affinda": "configured" if AFFINDA_API_KEY else "missing",
        "gemini": "configured" if GEMINI_API_KEY else "missing"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
