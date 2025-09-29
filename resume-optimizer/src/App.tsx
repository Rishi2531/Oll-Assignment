// ResumeOptimizer.tsx
import React, { useState, useRef } from "react";
import "./ResumeOptimizer.css";

// -------------------- Interfaces --------------------
interface SkillsAnalysis {
  total_skills?: number;
  top_skills?: string[];
  skills_found?: string[];
}

interface ExperienceAnalysis {
  total_years?: number;
  job_count?: number;
  recent_positions?: Array<{
    title?: string;
    company?: string;
    duration?: string;
  }>;
}

interface EducationAnalysis {
  degree_count?: number;
  highest_degree?: string | null;
  institutions?: string[];
}

interface ATSBreakdown {
  sections_found?: string[];
  has_contact_info?: boolean;
  skills_analysis?: SkillsAnalysis;
  experience_analysis?: ExperienceAnalysis;
  education_analysis?: EducationAnalysis;
}

interface ResumeAnalysis {
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  experience_years?: number;
  education_count?: number;
  skills_count?: number;
}

interface AnalysisResponse {
  success?: boolean;
  ats_score?: number;
  score_provider?: string;
  resume_analysis?: ResumeAnalysis;
  ats_breakdown?: ATSBreakdown;
  ai_recommendations?: string | null;
  analysis_report_url?: string | null;
  note?: string;
  error?: string;
}

// -------------------- Component --------------------
const ResumeOptimizer: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const progressIntervalRef = useRef<number | null>(null);

  // -------------------- Handlers --------------------
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const droppedFile = e.dataTransfer.files?.[0];
    if (!droppedFile) return;

    if (droppedFile.type === "application/pdf") {
      setFile(droppedFile);
      setError("");
    } else {
      setError("❌ Please upload a valid PDF file.");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.type === "application/pdf") {
        setFile(selectedFile);
        setError("");
      } else {
        setError("❌ Please upload a valid PDF file.");
      }
    }
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError("Please select a PDF resume first.");
      return;
    }

    setIsAnalyzing(true);
    setError("");
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (jobDescription) {
        formData.append("job_description", jobDescription);
      }

      // Fake upload progress
      progressIntervalRef.current = window.setInterval(() => {
        setUploadProgress((prev) => (prev >= 90 ? 90 : prev + 10));
      }, 400);

      const response = await fetch(
        "https://oll-assignment.onrender.com/analyze_resume/",
        {
          method: "POST",
          body: formData,
        }
      );

      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      setUploadProgress(100);

      const data: AnalysisResponse = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "❌ Resume analysis failed.");
      }

      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "⚠️ Something went wrong.");
    } finally {
      setIsAnalyzing(false);
      setUploadProgress(0);
    }
  };

  const resetForm = () => {
    setFile(null);
    setJobDescription("");
    setResult(null);
    setError("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // -------------------- Helpers --------------------
  const getScoreColor = (score = 0) => {
    if (score >= 80) return "#10b981";
    if (score >= 60) return "#f59e0b";
    return "#ef4444";
  };

  const getScoreMessage = (score = 0) => {
    if (score >= 80) return "✅ Excellent ATS Score!";
    if (score >= 70) return "👍 Good ATS Score";
    if (score >= 60) return "😐 Fair ATS Score";
    return "⚠️ Needs Optimization";
  };

  // Safe defaults
  const safeSections = result?.ats_breakdown?.sections_found || [];
  const safeTopSkills = result?.ats_breakdown?.skills_analysis?.top_skills || [];
  const safePositions =
    result?.ats_breakdown?.experience_analysis?.recent_positions || [];
  const safeInstitutions =
    result?.ats_breakdown?.education_analysis?.institutions || [];

  // -------------------- UI --------------------
  return (
    <div className="resume-optimizer">
      <div className="container">
        <header className="header">
          <h1>AI Resume ATS Optimizer</h1>
          <p>Upload your resume and get ATS scoring + AI optimization tips.</p>
        </header>

        {/* Upload Section */}
        {!result && (
          <div className="upload-section">
            <div
              className={`upload-area ${dragActive ? "drag-active" : ""} ${
                file ? "has-file" : ""
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="file-input"
                id="file-upload"
              />
              <div className="upload-content">
                {file ? (
                  <>
                    <h3>📄 {file.name}</h3>
                    <button
                      type="button"
                      className="change-file-btn"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      Change File
                    </button>
                  </>
                ) : (
                  <>
                    <h3>Drag & Drop your resume</h3>
                    <p>or</p>
                    <label htmlFor="file-upload" className="browse-btn">
                      Browse Files
                    </label>
                    <p className="file-requirements">PDF only, max 10MB</p>
                  </>
                )}
              </div>
            </div>

            <textarea
              placeholder="Paste job description (optional)..."
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
              rows={4}
            />

            {error && <div className="error-message">{error}</div>}

            <button
              onClick={handleAnalyze}
              disabled={!file || isAnalyzing}
              className="analyze-btn"
            >
              {isAnalyzing ? "Analyzing..." : "Analyze Resume"}
            </button>

            {isAnalyzing && (
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            )}
          </div>
        )}

        {/* Results Section */}
        {result && (
          <div className="results-section">
            <div className="score-card">
              <h2>ATS Score</h2>
              <div
                className="score-circle"
                style={{ borderColor: getScoreColor(result.ats_score) }}
              >
                <span>{result.ats_score ?? "--"}</span>
              </div>
              <p style={{ color: getScoreColor(result.ats_score) }}>
                {getScoreMessage(result.ats_score)}
              </p>
            </div>

            <div className="overview">
              <h3>Resume Overview</h3>
              <p>Name: {result.resume_analysis?.name || "Not found"}</p>
              <p>Email: {result.resume_analysis?.email || "Not found"}</p>
              <p>Phone: {result.resume_analysis?.phone || "Not found"}</p>
              <p>
                Experience: {result.resume_analysis?.experience_years || 0} yrs
              </p>
              <p>
                Education: {result.resume_analysis?.education_count || 0} entries
              </p>
              <p>Skills: {result.resume_analysis?.skills_count || 0}</p>
            </div>

            <div className="breakdown">
              <h3>ATS Breakdown</h3>
              <p>
                Sections Found:{" "}
                {safeSections.length > 0
                  ? safeSections.join(", ")
                  : "None detected"}
              </p>
              <p>
                Contact Info:{" "}
                {result.ats_breakdown?.has_contact_info ? "✅ Yes" : "❌ No"}
              </p>
              <p>
                Skills: {safeTopSkills.length > 0 ? safeTopSkills.join(", ") : "—"}
              </p>
              <p>
                Positions:{" "}
                {safePositions.length > 0
                  ? safePositions.map((p) => p.title).join(", ")
                  : "—"}
              </p>
              <p>
                Education:{" "}
                {safeInstitutions.length > 0
                  ? safeInstitutions.join(", ")
                  : "—"}
              </p>
            </div>

            {result.ai_recommendations && (
              <div className="ai-recs">
                <h3>🤖 AI Recommendations</h3>
                <pre>{result.ai_recommendations}</pre>
              </div>
            )}

            <div className="actions">
              {result.analysis_report_url && (
                <a
                  href={`https://oll-assignment.onrender.com${result.analysis_report_url}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="download-btn"
                >
                  📊 Download Full Report
                </a>
              )}
              <button onClick={resetForm} className="reset-btn">
                🔄 Analyze Another
              </button>
            </div>
          </div>
        )}

        <footer className="footer">
          <small>Powered by Affinda + Gemini AI</small>
        </footer>
      </div>
    </div>
  );
};

export default ResumeOptimizer;
