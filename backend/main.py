import os
import requests
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
import tempfile
import pdfplumber
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv  # Add this import

# Load environment variables for local development
load_dotenv()

# --- API Keys ---
AFFINDA_API_KEY = os.getenv("AFFINDA_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Affinda API configuration
AFFINDA_API_URL = "https://api.affinda.com/v2/resumes"
AFFINDA_HEADERS = {
    "Authorization": f"Bearer {AFFINDA_API_KEY}",
}

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

# --- Affinda API Resume Parsing with ATS Score ---
def parse_resume_with_affinda(file_path: str):
    """
    Use Affinda API for professional resume parsing including ATS score
    Returns the full parsed data from Affinda
    """
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
            return response.json()  # Return full Affinda response
        else:
            error_msg = f"Affinda API error: {response.status_code} - {response.text}"
            print(error_msg)
            return {"error": error_msg}
            
    except Exception as e:
        print(f"Affinda API call failed: {e}")
        return {"error": str(e)}

# --- Extract ATS Score from Affinda Response ---
def extract_affinda_ats_score(affinda_data: dict):
    """
    Extract ATS score and detailed analysis from Affinda response
    """
    if "error" in affinda_data:
        return {
            "score": 0,
            "note": "Affinda parsing failed",
            "details": affinda_data
        }
    
    # Get ATS score from Affinda (they provide it directly)
    ats_score = affinda_data.get("atsScore", {})
    raw_score = ats_score.get("score")
    
    # Convert to 0-100 scale if needed
    if raw_score is not None:
        if raw_score <= 1.0:  # If score is 0-1 scale
            score = round(raw_score * 100, 1)
        else:
            score = round(raw_score, 1)
    else:
        # Fallback: Calculate score based on data completeness
        score = calculate_fallback_score(affinda_data)
    
    # Extract detailed analysis
    sections_found = []
    if affinda_data.get("education"):
        sections_found.append("education")
    if affinda_data.get("workExperience"):
        sections_found.append("experience") 
    if affinda_data.get("skills"):
        sections_found.append("skills")
    if affinda_data.get("summary"):
        sections_found.append("summary")
    
    # Contact info
    has_contact = bool(
        affinda_data.get("emails") or 
        affinda_data.get("phoneNumbers") or
        affinda_data.get("websites")
    )
    
    # Skills analysis
    skills = affinda_data.get("skills", [])
    skills_count = len(skills)
    top_skills = [skill.get("name") for skill in skills[:10] if skill.get("name")]
    
    # Experience analysis
    experience_years = affinda_data.get("totalYearsExperience", 0)
    work_experience = affinda_data.get("workExperience", [])
    
    # Education analysis
    education = affinda_data.get("education", [])
    
    return {
        "score": score,
        "sections_found": sections_found,
        "has_contact_info": has_contact,
        "skills_analysis": {
            "total_skills": skills_count,
            "top_skills": top_skills,
            "skills_found": [skill.get("name") for skill in skills if skill.get("name")]
        },
        "experience_analysis": {
            "total_years": experience_years,
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
        "affinda_ats_breakdown": ats_score  # Include Affinda's original ATS breakdown
    }

def calculate_fallback_score(affinda_data: dict):
    """
    Fallback scoring when Affinda doesn't provide direct ATS score
    """
    score = 50.0  # Base score
    
    # Education (20 points max)
    if affinda_data.get("education"):
        score += min(len(affinda_data["education"]) * 5, 20)
    
    # Work Experience (25 points max)
    if affinda_data.get("workExperience"):
        score += min(len(affinda_data["workExperience"]) * 5, 25)
    
    # Skills (15 points max)
    if affinda_data.get("skills"):
        score += min(len(affinda_data["skills"]) * 1.5, 15)
    
    # Contact Info (10 points)
    if affinda_data.get("emails") or affinda_data.get("phoneNumbers"):
        score += 10
    
    # Ensure score is within bounds
    return max(0, min(100, round(score, 1)))

# --- AI Enhancement ---
def enhance_resume_with_gemini(affinda_data: dict, ats_score: float, job_description: str = None):
    if not GEMINI_API_KEY:
        return "AI enhancement not available - Gemini API key missing"
    
    try:
        # Prepare structured data for AI enhancement
        score_analysis = f"Current ATS Score: {ats_score}/100 (provided by Affinda)"
        
        resume_info = f"""
        Resume Analysis from Affinda:
        - Name: {affinda_data.get('name', {}).get('raw', 'Not found')}
        - Email: {affinda_data.get('emails', ['Not found'])[0] if affinda_data.get('emails') else 'Not found'}
        - Phone: {affinda_data.get('phoneNumbers', ['Not found'])[0] if affinda_data.get('phoneNumbers') else 'Not found'}
        - Education: {len(affinda_data.get('education', []))} institutions found
        - Experience: {len(affinda_data.get('workExperience', []))} positions, {affinda_data.get('totalYearsExperience', 0)} years
        - Skills: {len(affinda_data.get('skills', []))} skills identified
        - Summary: {affinda_data.get('summary', 'Not provided')}
        - {score_analysis}
        """
        
        prompt = f"""As an expert ATS resume optimizer, analyze this resume data and provide specific recommendations to improve the ATS score:

        {resume_info}

        Based on the Affinda ATS score of {ats_score}/100, provide:

        1. QUICK WINS: Immediate improvements that could boost ATS score by 10+ points
        2. SKILLS OPTIMIZATION: Missing or weak skills sections
        3. KEYWORD OPTIMIZATION: ATS keywords to include
        4. FORMATTING TIPS: ATS-friendly formatting recommendations
        5. CONTENT GAPS: Missing sections or information

        Focus on actionable, specific recommendations.
        """
        
        if job_description:
            prompt += f"\nTARGET JOB DESCRIPTION:\n{job_description}\n\nTailor recommendations specifically for this role and include relevant keywords from the job description."

        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        return f"AI enhancement failed: {str(e)}"

# --- Save Enhanced Resume ---
def save_enhanced_resume(affinda_data: dict, ats_score: float, recommendations: str, output_path: str):
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("AFFINDA RESUME ATS ANALYSIS REPORT\n")
            f.write("=" * 50 + "\n\n")
            
            f.write("RESUME SUMMARY:\n")
            f.write("-" * 20 + "\n")
            f.write(f"Name: {affinda_data.get('name', {}).get('raw', 'N/A')}\n")
            f.write(f"Email: {affinda_data.get('emails', ['N/A'])[0] if affinda_data.get('emails') else 'N/A'}\n")
            f.write(f"ATS Score: {ats_score}/100\n")
            f.write(f"Experience: {affinda_data.get('totalYearsExperience', 0)} years\n")
            f.write(f"Education: {len(affinda_data.get('education', []))} entries\n")
            f.write(f"Skills: {len(affinda_data.get('skills', []))} identified\n\n")
            
            f.write("ATS ANALYSIS:\n")
            f.write("-" * 15 + "\n")
            f.write(f"Score provided by Affinda API\n")
            f.write(f"Note: ATS scores evaluate resume parsing quality and ATS compatibility\n\n")
            
            f.write("AI OPTIMIZATION RECOMMENDATIONS:\n")
            f.write("-" * 35 + "\n")
            f.write(recommendations)
            
            f.write("\n\nDETAILED DATA (from Affinda):\n")
            f.write("-" * 30 + "\n")
            f.write(f"Full analysis available via Affinda API\n")
            
        return True
    except Exception as e:
        print(f"File creation failed: {e}")
        return False

# --- FastAPI Endpoints ---
@app.get("/")
async def root():
    return {"message": "AI Resume ATS Optimizer API with Affinda ATS Scoring"}

@app.post("/analyze_resume/")
async def analyze_resume(file: UploadFile = File(...), job_description: str = Form(None)):
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

        # Parse resume with Affinda
        print("Parsing resume with Affinda API...")
        affinda_data = parse_resume_with_affinda(input_pdf)
        
        # Extract ATS score from Affinda
        print("Extracting ATS score from Affinda...")
        score_data = extract_affinda_ats_score(affinda_data)

        # Get AI recommendations based on Affinda score
        print("Generating AI recommendations...")
        recommendations = enhance_resume_with_gemini(affinda_data, score_data["score"], job_description)

        # Save analysis results
        enhanced_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
        save_success = save_enhanced_resume(
            affinda_data, 
            score_data["score"], 
            recommendations, 
            enhanced_file
        )

        # Prepare response
        response_data = {
            "success": True,
            "ats_score": score_data["score"],
            "score_provider": "Affinda API",
            "resume_analysis": {
                "name": affinda_data.get("name", {}).get("raw"),
                "email": affinda_data.get("emails", [None])[0],
                "phone": affinda_data.get("phoneNumbers", [None])[0],
                "experience_years": affinda_data.get("totalYearsExperience", 0),
                "education_count": len(affinda_data.get("education", [])),
                "experience_count": len(affinda_data.get("workExperience", [])),
                "skills_count": len(affinda_data.get("skills", []))
            },
            "ats_breakdown": {
                "sections_found": score_data["sections_found"],
                "has_contact_info": score_data["has_contact_info"],
                "skills_analysis": score_data["skills_analysis"],
                "experience_analysis": score_data["experience_analysis"],
                "education_analysis": score_data["education_analysis"]
            },
            "ai_recommendations_available": bool(recommendations and "failed" not in recommendations),
            "analysis_report_url": f"/download/{Path(enhanced_file).name}" if save_success else None,
            "note": score_data["note"]
        }

        # Cleanup
        try:
            os.unlink(input_pdf)
        except:
            pass

        return JSONResponse(response_data)

    except Exception as e:
        import traceback
        print("❌ Error analyzing resume:")
        traceback.print_exc()
        return JSONResponse({"error": f"Analysis failed: {str(e)}"}, status_code=500)

@app.get("/download/{filename}")
async def download_file(filename: str):
    try:
        file_path = os.path.join(tempfile.gettempdir(), filename)
        if not os.path.exists(file_path):
            return JSONResponse({"error": "File not found or expired"}, status_code=404)
        return FileResponse(file_path, media_type="text/plain", filename="resume_ats_analysis.txt")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health_check():
    # Test Affinda connection
    affinda_status = "configured" if AFFINDA_API_KEY else "missing"
    gemini_status = "configured" if GEMINI_API_KEY else "missing"
    
    return {
        "status": "healthy", 
        "services": {
            "affinda": affinda_status,
            "gemini": gemini_status
        },
        "environment": "production" if os.getenv("RENDER") else "development"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)