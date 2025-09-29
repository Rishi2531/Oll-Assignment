import os
import requests
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
import tempfile
import pdfplumber
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import base64

# --- API Keys ---
AFFINDA_API_KEY = os.getenv("AFFINDA_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MAGICAL_API_KEY = os.getenv("MAGICAL_API_KEY")

# Affinda API configuration
AFFINDA_API_URL = "https://api.affinda.com/v2/resumes"
AFFINDA_HEADERS = {
    "Authorization": f"Bearer {AFFINDA_API_KEY}",
    "X-API-KEY": AFFINDA_API_KEY
}

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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

# --- Affinda API Resume Scoring ---
def get_affinda_score(file_path: str):
    """
    Use Affinda API for professional ATS resume scoring
    """
    if not AFFINDA_API_KEY:
        return {"error": "Affinda API key not configured", "note": "API key missing"}

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
            data = response.json()
            
            # Extract ATS score and details from Affinda response
            ats_score = data.get("atsScore", {}).get("score", 0) * 100  # Convert to 0-100 scale
            
            # Extract sections found
            sections_found = []
            if data.get("education"):
                sections_found.append("education")
            if data.get("workExperience"):
                sections_found.append("experience")
            if data.get("skills"):
                sections_found.append("skills")
            if data.get("summary"):
                sections_found.append("summary")
            
            # Extract contact info
            contact_info = data.get("phone") or data.get("email") or data.get("website")
            
            # Calculate word count from extracted text
            raw_text = data.get("raw_text", "")
            word_count = len(raw_text.split()) if raw_text else 0
            
            return {
                "score": round(ats_score, 1),
                "sections_found": sections_found,
                "word_count": word_count,
                "has_contact_info": bool(contact_info),
                "note": "Scored via Affinda API",
                "affinda_data": {  # Additional useful data from Affinda
                    "predicted_job_titles": data.get("predictedJobTitles", []),
                    "years_of_experience": data.get("yearsOfExperience", 0),
                    "skills": [skill.get("name", "") for skill in data.get("skills", [])][:10]
                }
            }
        else:
            error_msg = f"Affinda API error: {response.status_code} - {response.text}"
            print(error_msg)
            return {"error": error_msg, "note": "Affinda API failed"}
            
    except Exception as e:
        print(f"Affinda API call failed: {e}")
        return {"error": str(e), "note": "Affinda API call failed"}

# --- Fallback Scoring Methods ---
def get_magicalapi_score(file_path: str):
    """Fallback to MagicalAPI if Affinda fails"""
    if not MAGICAL_API_KEY:
        return {"error": "MagicalAPI key not configured"}
    
    try:
        # Upload file to temporary hosting
        with open(file_path, "rb") as file:
            upload_response = requests.post(
                "https://file.io",
                files={"file": file},
                params={"expires": "1h"}
            )
        
        if upload_response.status_code == 200:
            file_data = upload_response.json()
            file_url = file_data.get("link")
            
            # Score with MagicalAPI
            headers = {"Authorization": f"Bearer {MAGICAL_API_KEY}"}
            score_response = requests.post(
                "https://api.magicalapi.com/v1/resume/score",
                headers=headers,
                json={"resume_url": file_url},
                timeout=60
            )
            
            if score_response.status_code == 200:
                data = score_response.json()
                data["note"] = "Scored via MagicalAPI"
                return data
                
    except Exception as e:
        print(f"MagicalAPI fallback failed: {e}")
    
    return {"error": "MagicalAPI fallback failed"}

def get_local_score(file_path: str):
    """Final fallback - simple rule-based scoring"""
    text = extract_text_from_pdf(file_path)
    if not text:
        return {"score": 0, "sections_found": [], "word_count": 0, "has_contact_info": False, "note": "No text extracted"}
    
    score = 50.0
    sections = ["experience", "education", "skills", "projects", "summary"]
    found_sections = []
    
    for section in sections:
        if section in text.lower():
            found_sections.append(section)
            score += 8.0

    word_count = len(text.split())
    if 300 <= word_count <= 800:
        score += 15.0
    elif 800 < word_count <= 1200:
        score += 10.0
    elif word_count > 1200:
        score -= 5.0

    contact_found = any(indicator in text.lower() for indicator in ["@", "phone", "email", "linkedin"])
    if contact_found:
        score += 12.0

    # Check for action verbs
    action_verbs = ["managed", "developed", "created", "led", "implemented", "achieved"]
    verbs_found = sum(1 for verb in action_verbs if verb in text.lower())
    score += min(verbs_found * 2, 10.0)

    score = max(0, min(100, score))
    
    return {
        "score": round(score, 1),
        "sections_found": found_sections,
        "word_count": word_count,
        "has_contact_info": contact_found,
        "note": "Rule-based scoring (fallback)"
    }

# --- Main Scoring Function ---
def get_resume_score(file_path: str):
    """
    Try scoring methods in order:
    1. Affinda API (professional ATS scoring)
    2. MagicalAPI (fallback)
    3. Local rule-based (final fallback)
    """
    # Try Affinda first
    affinda_result = get_affinda_score(file_path)
    if "score" in affinda_result:
        return affinda_result
    
    # Try MagicalAPI as fallback
    magical_result = get_magicalapi_score(file_path)
    if "score" in magical_result:
        return magical_result
    
    # Final fallback to local scoring
    return get_local_score(file_path)

# --- AI Enhancement (Keep your existing Gemini function) ---
def enhance_resume_with_gemini(text: str, job_description: str = None):
    if not GEMINI_API_KEY:
        return text + "\n\n[AI Enhancement not available - API key missing]"
    
    prompt = f"""You are an expert ATS resume optimizer. Analyze and enhance this resume to maximize ATS compatibility and professional appeal:

RESUME:
{text}

"""
    if job_description:
        prompt += f"""TARGET JOB DESCRIPTION:
{job_description}

Please tailor the resume specifically for this role while maintaining ATS compatibility."""

    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        return text + "\n\n[Enhanced with AI - some features limited]"

# --- Save Enhanced Resume ---
def save_enhanced_resume(text: str, output_path: str):
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("AI-ENHANCED RESUME\n")
            f.write("=" * 60 + "\n\n")
            f.write("Optimized for ATS compatibility and professional impact\n\n")
            f.write(text)
        return True
    except Exception as e:
        print(f"File creation failed: {e}")
        return False

# --- FastAPI Endpoints ---
@app.get("/")
async def root():
    return {"message": "AI Resume ATS Optimizer API with Affinda Integration"}

@app.post("/optimize_resume/")
async def optimize_resume(file: UploadFile = File(...), job_description: str = Form(None)):
    try:
        if not file.filename.lower().endswith('.pdf'):
            return JSONResponse({"error": "Only PDF files are supported"}, status_code=400)

        # Save uploaded file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            if len(content) == 0:
                return JSONResponse({"error": "Uploaded file is empty"}, status_code=400)
            tmp.write(content)
            input_pdf = tmp.name

        # Extract text
        extracted_text = extract_text_from_pdf(input_pdf)
        if not extracted_text or len(extracted_text.strip()) < 50:
            return JSONResponse({"error": "Could not extract sufficient text from PDF"}, status_code=400)

        # Get before score
        print("Getting initial ATS score via Affinda...")
        before_score_data = get_resume_score(input_pdf)

        # Enhance resume
        print("Enhancing resume with AI...")
        enhanced_text = enhance_resume_with_gemini(extracted_text, job_description)

        # Save enhanced version
        enhanced_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
        save_enhanced_resume(enhanced_text, enhanced_file)

        # Get after score (using same file since we can't easily rescore text)
        after_score_data = get_resume_score(input_pdf)

        # Prepare response
        response_data = {
            "before_score": before_score_data.get("score", 0),
            "after_score": after_score_data.get("score", 0),
            "score_improvement": round(after_score_data.get("score", 0) - before_score_data.get("score", 0), 1),
            "before_details": before_score_data,
            "after_details": after_score_data,
            "enhanced_resume_url": f"/download/{Path(enhanced_file).name}",
            "text_extracted": True,
            "text_length": len(extracted_text),
            "scoring_method": before_score_data.get("note", "Unknown")
        }

        # Cleanup
        try:
            os.unlink(input_pdf)
        except:
            pass

        return JSONResponse(response_data)

    except Exception as e:
        import traceback
        print("❌ Error optimizing resume:")
        traceback.print_exc()
        return JSONResponse({"error": f"Optimization failed: {str(e)}"}, status_code=500)

@app.get("/download/{filename}")
async def download_file(filename: str):
    try:
        file_path = os.path.join(tempfile.gettempdir(), filename)
        if not os.path.exists(file_path):
            return JSONResponse({"error": "File not found or expired"}, status_code=404)
        return FileResponse(file_path, media_type="text/plain", filename="enhanced_resume.txt")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "services": {
            "affinda": bool(AFFINDA_API_KEY),
            "gemini": bool(GEMINI_API_KEY),
            "magicalapi": bool(MAGICAL_API_KEY)
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)