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

# Configure Gemini with proper error handling
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("✅ Gemini API configured successfully")
    except Exception as e:
        print(f"❌ Gemini configuration failed: {e}")
        GEMINI_API_KEY = None  # Disable Gemini if configuration fails

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

# --- Calculate ATS Score from Affinda Data ---
def calculate_ats_score_from_affinda(affinda_data: dict):
    """
    Calculate ATS score based on Affinda parsed data
    """
    if "error" in affinda_data:
        return {
            "score": 0,
            "sections_found": [],
            "has_contact_info": False,
            "note": "Affinda parsing failed",
            "details": affinda_data
        }
    
    # Get the actual data from Affinda response
    data = affinda_data  # The main response IS the data
    
    score = 50.0  # Base score
    
    # Extract sections and calculate score
    sections_found = []
    
    # Education section (20 points)
    if data.get("education"):
        sections_found.append("education")
        education_count = len(data["education"])
        score += min(education_count * 5, 20)
    
    # Work Experience section (25 points)
    if data.get("workExperience"):
        sections_found.append("experience")
        experience_count = len(data["workExperience"])
        score += min(experience_count * 5, 25)
    
    # Skills section (15 points)
    if data.get("skills"):
        sections_found.append("skills")
        skills_count = len(data["skills"])
        score += min(skills_count * 1.5, 15)
    
    # Summary/Objective section (10 points)
    if data.get("summary") or data.get("objective"):
        sections_found.append("summary")
        score += 10
    
    # Contact Information (10 points)
    has_contact_info = bool(
        data.get("emails") or 
        data.get("phoneNumbers") or
        data.get("websites")
    )
    if has_contact_info:
        score += 10
    
    # Experience years bonus (5 points)
    experience_years = data.get("totalYearsExperience", 0)
    if experience_years >= 2:
        score += min(experience_years, 5)
    
    # Skills density bonus (5 points)
    skills_count = len(data.get("skills", []))
    if skills_count >= 10:
        score += 5
    elif skills_count >= 5:
        score += 2
    
    # Ensure score is within bounds
    score = max(0, min(100, round(score, 1)))
    
    # Prepare detailed analysis
    skills = data.get("skills", [])
    work_experience = data.get("workExperience", [])
    education = data.get("education", [])
    
    return {
        "score": score,
        "sections_found": sections_found,
        "has_contact_info": has_contact_info,
        "skills_analysis": {
            "total_skills": len(skills),
            "top_skills": [skill.get("name") for skill in skills[:10] if skill.get("name")],
            "skills_found": [skill.get("name") for skill in skills if skill.get("name")]
        },
        "experience_analysis": {
            "total_years": experience_years,
            "job_count": len(work_experience),
            "recent_positions": [
                {
                    "title": exp.get("jobTitle", "Unknown"),
                    "company": exp.get("organization", "Unknown"),
                    "duration": exp.get("dates", {}).get("rawText", "Unknown")
                }
                for exp in work_experience[:3]
            ]
        },
        "education_analysis": {
            "degree_count": len(education),
            "highest_degree": education[0].get("accreditation", {}).get("education") if education else None,
            "institutions": [edu.get("organization", "Unknown") for edu in education if edu.get("organization")]
        },
        "note": "ATS scoring based on Affinda parsed data"
    }

# --- AI Enhancement with Working Gemini Models ---
def enhance_resume_with_gemini(affinda_data: dict, ats_score: float, job_description: str = None):
    if not GEMINI_API_KEY:
        return "AI enhancement not available - Gemini API key missing"
    
    try:
        # Prepare structured data for AI enhancement
        resume_info = f"""
        Resume Analysis from Affinda:
        - Name: {affinda_data.get('name', {}).get('raw', 'Not found')}
        - Email: {affinda_data.get('emails', ['Not found'])[0] if affinda_data.get('emails') else 'Not found'}
        - Phone: {affinda_data.get('phoneNumbers', ['Not found'])[0] if affinda_data.get('phoneNumbers') else 'Not found'}
        - Education: {len(affinda_data.get('education', []))} institutions found
        - Experience: {len(affinda_data.get('workExperience', []))} positions, {affinda_data.get('totalYearsExperience', 0)} years
        - Skills: {len(affinda_data.get('skills', []))} skills identified
        - Current ATS Score: {ats_score}/100
        """
        
        prompt = f"""As an expert ATS resume optimizer, analyze this resume data and provide specific recommendations:

        {resume_info}

        Based on the ATS score of {ats_score}/100, provide:

        1. QUICK WINS: Immediate improvements for ATS compatibility
        2. SKILLS OPTIMIZATION: Missing or weak skills sections
        3. KEYWORD OPTIMIZATION: ATS keywords to include
        4. FORMATTING TIPS: ATS-friendly formatting
        5. CONTENT GAPS: Missing sections

        Focus on actionable, specific recommendations.
        """
        
        if job_description:
            prompt += f"\nTARGET JOB DESCRIPTION:\n{job_description}\n\nTailor recommendations for this role."

        # Get available models and find a working one
        try:
            available_models = genai.list_models()
            model_names = [model.name for model in available_models]
            print(f"Available Gemini models: {model_names}")
            
            # Try different model names that might work
            possible_models = [
                'gemini-1.5-pro',
                'gemini-1.0-pro',
                'gemini-pro',
                'models/gemini-pro'
            ]
            
            working_model = None
            for model_name in possible_models:
                if any(model_name in name for name in model_names):
                    try:
                        model = genai.GenerativeModel(model_name)
                        # Test with a short prompt
                        test_response = model.generate_content("Hello", request_options={"timeout": 10})
                        working_model = model
                        print(f"✅ Using Gemini model: {model_name}")
                        break
                    except Exception as e:
                        print(f"❌ Model {model_name} test failed: {e}")
                        continue
            
            if not working_model:
                return "AI enhancement not available - No working Gemini models found"
            
            # Generate the actual response
            response = working_model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            print(f"Gemini model discovery failed: {e}")
            return f"AI enhancement failed: {str(e)}"
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        return f"AI enhancement failed: {str(e)}"

# --- Save Analysis Report ---
def save_analysis_report(affinda_data: dict, ats_score: float, recommendations: str, output_path: str):
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("RESUME ATS ANALYSIS REPORT\n")
            f.write("=" * 40 + "\n\n")
            
            f.write("RESUME SUMMARY:\n")
            f.write("-" * 20 + "\n")
            f.write(f"Name: {affinda_data.get('name', {}).get('raw', 'N/A')}\n")
            f.write(f"Email: {affinda_data.get('emails', ['N/A'])[0] if affinda_data.get('emails') else 'N/A'}\n")
            f.write(f"ATS Score: {ats_score}/100\n")
            f.write(f"Experience: {affinda_data.get('totalYearsExperience', 0)} years\n")
            f.write(f"Education: {len(affinda_data.get('education', []))} entries\n")
            f.write(f"Skills: {len(affinda_data.get('skills', []))} identified\n\n")
            
            f.write("AI OPTIMIZATION RECOMMENDATIONS:\n")
            f.write("-" * 35 + "\n")
            f.write(recommendations if recommendations else "AI recommendations not available at this time.")
            
        return True
    except Exception as e:
        print(f"File creation failed: {e}")
        return False

# --- FastAPI Endpoints ---
@app.get("/")
async def root():
    return {"message": "AI Resume ATS Analyzer API with Affinda Integration"}

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
        
        # Calculate ATS score from Affinda data
        print("Calculating ATS score...")
        score_data = calculate_ats_score_from_affinda(affinda_data)

        # Get AI recommendations
        print("Generating AI recommendations...")
        recommendations = enhance_resume_with_gemini(affinda_data, score_data["score"], job_description)

        # Save analysis results
        enhanced_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt").name
        save_success = save_analysis_report(
            affinda_data, 
            score_data["score"], 
            recommendations, 
            enhanced_file
        )

        # Prepare response
        response_data = {
            "success": True,
            "ats_score": score_data["score"],
            "score_provider": "Affinda API + Custom ATS Algorithm",
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
                "sections_found": score_data.get("sections_found", []),
                "has_contact_info": score_data.get("has_contact_info", False),
                "skills_analysis": score_data.get("skills_analysis", {}),
                "experience_analysis": score_data.get("experience_analysis", {}),
                "education_analysis": score_data.get("education_analysis", {})
            },
            "ai_recommendations_available": bool(recommendations and 
                "failed" not in recommendations.lower() and 
                "not available" not in recommendations.lower() and
                "error" not in recommendations.lower()),
            "analysis_report_url": f"/download/{Path(enhanced_file).name}" if save_success else None,
            "note": score_data.get("note", "Analysis complete")
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
        return FileResponse(file_path, media_type="text/plain", filename="resume_analysis.txt")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health_check():
    affinda_status = "configured" if AFFINDA_API_KEY else "missing"
    gemini_status = "configured" if GEMINI_API_KEY else "missing"
    
    # Test Gemini models
    gemini_models_working = False
    available_models = []
    
    if GEMINI_API_KEY:
        try:
            models = genai.list_models()
            available_models = [model.name for model in models]
            gemini_models = [name for name in available_models if 'gemini' in name.lower()]
            gemini_models_working = len(gemini_models) > 0
            print(f"Available Gemini models: {gemini_models}")
        except Exception as e:
            print(f"Gemini model check failed: {e}")
    
    return {
        "status": "healthy", 
        "services": {
            "affinda": affinda_status,
            "gemini": gemini_status,
            "gemini_models_working": gemini_models_working,
            "available_models": available_models[:5]  # Show first 5 models
        },
        "environment": "production" if os.getenv("RENDER") else "development"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)