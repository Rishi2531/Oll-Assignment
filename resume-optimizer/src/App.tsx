import React, { useState, useRef } from 'react';
import './ResumeOptimizer.css';

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
  experience_count?: number;
  skills_count?: number;
}

interface AnalysisResponse {
  success?: boolean;
  ats_score?: number;
  score_provider?: string;
  resume_analysis?: ResumeAnalysis;
  ats_breakdown?: ATSBreakdown;
  ai_recommendations_available?: boolean;
  analysis_report_url?: string | null;
  note?: string;
}

const ResumeOptimizer: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const progressIntervalRef = useRef<number | null>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      if (droppedFile.type === 'application/pdf') {
        setFile(droppedFile);
        setError('');
      } else setError('Please upload a PDF file');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError('');
    }
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError('Please select a PDF file');
      return;
    }

    setIsAnalyzing(true);
    setError('');
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (jobDescription) formData.append('job_description', jobDescription);

      // Upload progress simulation
      progressIntervalRef.current = window.setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
            return 90;
          }
          return prev + 10;
        });
      }, 500);

      const response = await fetch('https://oll-assignment.onrender.com/analyze_resume/', {
        method: 'POST',
        body: formData,
      });

      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      setUploadProgress(100);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Analysis failed');
      }

      const data: AnalysisResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsAnalyzing(false);
      setUploadProgress(0);
    }
  };

  const downloadAnalysisReport = () => {
    if (result?.analysis_report_url) {
      window.open(`https://oll-assignment.onrender.com${result.analysis_report_url}`, '_blank');
    }
  };

  const resetForm = () => {
    setFile(null);
    setJobDescription('');
    setResult(null);
    setError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const getScoreColor = (score: number = 0) => {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#f59e0b';
    return '#ef4444';
  };

  const getScoreMessage = (score: number = 0) => {
    if (score >= 80) return 'Excellent ATS Score!';
    if (score >= 70) return 'Good ATS Score';
    if (score >= 60) return 'Fair ATS Score';
    return 'Needs ATS Optimization';
  };

  const getScoreLevel = (score: number = 0) => {
    if (score >= 80) return 'Excellent';
    if (score >= 70) return 'Good';
    if (score >= 60) return 'Fair';
    return 'Poor';
  };

  // Safe array access helpers
  const safeSectionsFound = result?.ats_breakdown?.sections_found || [];
  const safeTopSkills = result?.ats_breakdown?.skills_analysis?.top_skills || [];
  const safeRecentPositions = result?.ats_breakdown?.experience_analysis?.recent_positions || [];
  const safeInstitutions = result?.ats_breakdown?.education_analysis?.institutions || [];

  return (
    <div className="resume-optimizer">
      <div className="container">
        <header className="header">
          <h1>AI Resume ATS Analyzer</h1>
          <p>Get professional ATS scoring and optimization recommendations powered by Affinda API</p>
        </header>

        {!result ? (
          <div className="upload-section">
            <div
              className={`upload-area ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
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
                <div className="upload-icon">📄</div>
                {file ? (
                  <>
                    <h3>Selected File</h3>
                    <p className="file-name">{file.name}</p>
                    <button type="button" className="change-file-btn" onClick={() => fileInputRef.current?.click()}>
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
                    <p className="file-requirements">PDF files only, max 10MB</p>
                  </>
                )}
              </div>
            </div>

            <div className="job-description-section">
              <label htmlFor="job-description" className="section-label">
                Job Description (Optional)
              </label>
              <textarea
                id="job-description"
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Paste the job description here for targeted optimization recommendations..."
                rows={4}
              />
              <p className="helper-text">Adding a job description will provide tailored optimization suggestions</p>
            </div>

            {error && (
              <div className="error-message">
                <span className="error-icon">⚠️</span>
                {error}
              </div>
            )}

            <button 
              onClick={handleAnalyze} 
              disabled={!file || isAnalyzing} 
              className={`analyze-btn ${isAnalyzing ? 'analyzing' : ''}`}
            >
              {isAnalyzing ? (
                <>
                  <span className="spinner"></span>
                  Analyzing...
                </>
              ) : (
                'Analyze Resume ATS Score'
              )}
            </button>

            {isAnalyzing && (
              <div className="progress-section">
                <div className="progress-bar">
                  <div 
                    className="progress-fill" 
                    style={{ width: `${uploadProgress}%` }}
                  ></div>
                </div>
                <p>Parsing resume with Affinda API...</p>
              </div>
            )}
          </div>
        ) : (
          <div className="results-section">
            {/* Main Score Card */}
            <div className="main-score-card">
              <div className="score-header">
                <h2>ATS Resume Score</h2>
                <span className="score-provider">Powered by {result.score_provider || 'Affinda API'}</span>
              </div>
              <div className="main-score-display">
                <div 
                  className="score-circle-large" 
                  style={{ borderColor: getScoreColor(result.ats_score) }}
                >
                  <span className="score-value-large">{result.ats_score || 0}</span>
                  <span className="score-label">/ 100</span>
                </div>
                <div className="score-info">
                  <h3 
                    className="score-level" 
                    style={{ color: getScoreColor(result.ats_score) }}
                  >
                    {getScoreLevel(result.ats_score)}
                  </h3>
                  <p className="score-message">{getScoreMessage(result.ats_score)}</p>
                  <p className="score-note">{result.note || 'Analysis complete'}</p>
                </div>
              </div>
            </div>

            {/* Resume Overview */}
            <div className="resume-overview">
              <h3>Resume Overview</h3>
              <div className="overview-grid">
                <div className="overview-item">
                  <span className="overview-label">Name</span>
                  <span className="overview-value">{result.resume_analysis?.name || 'Not detected'}</span>
                </div>
                <div className="overview-item">
                  <span className="overview-label">Email</span>
                  <span className="overview-value">{result.resume_analysis?.email || 'Not detected'}</span>
                </div>
                <div className="overview-item">
                  <span className="overview-label">Phone</span>
                  <span className="overview-value">{result.resume_analysis?.phone || 'Not detected'}</span>
                </div>
                <div className="overview-item">
                  <span className="overview-label">Experience</span>
                  <span className="overview-value">{result.resume_analysis?.experience_years || 0} years</span>
                </div>
                <div className="overview-item">
                  <span className="overview-label">Education</span>
                  <span className="overview-value">{result.resume_analysis?.education_count || 0} entries</span>
                </div>
                <div className="overview-item">
                  <span className="overview-label">Skills</span>
                  <span className="overview-value">{result.resume_analysis?.skills_count || 0} identified</span>
                </div>
              </div>
            </div>

            {/* ATS Breakdown */}
            <div className="breakdown-section">
              <h3>ATS Breakdown</h3>
              
              {/* Sections Found */}
              <div className="breakdown-category">
                <h4>Resume Sections</h4>
                <div className="sections-list">
                  {safeSectionsFound.map((section, index) => (
                    <span key={index} className="section-tag present">
                      ✓ {section}
                    </span>
                  ))}
                  {['education', 'experience', 'skills'].filter(section => 
                    !safeSectionsFound.includes(section)
                  ).map((section, index) => (
                    <span key={index} className="section-tag missing">
                      ✗ {section}
                    </span>
                  ))}
                </div>
              </div>

              {/* Contact Info */}
              <div className="breakdown-category">
                <h4>Contact Information</h4>
                <span className={`status ${result.ats_breakdown?.has_contact_info ? 'present' : 'missing'}`}>
                  {result.ats_breakdown?.has_contact_info ? '✓ Complete' : '✗ Incomplete'}
                </span>
              </div>

              {/* Skills Analysis */}
              <div className="breakdown-category">
                <h4>Skills Analysis</h4>
                <p>
                  <strong>{result.ats_breakdown?.skills_analysis?.total_skills || 0}</strong> skills detected
                </p>
                <div className="skills-list">
                  {safeTopSkills.map((skill, index) => (
                    <span key={index} className="skill-tag">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>

              {/* Experience Analysis */}
              <div className="breakdown-category">
                <h4>Experience</h4>
                <p>
                  <strong>{result.ats_breakdown?.experience_analysis?.job_count || 0}</strong> positions •{' '}
                  <strong>{result.ats_breakdown?.experience_analysis?.total_years || 0}</strong> years
                </p>
                {safeRecentPositions.length > 0 && (
                  <div className="positions-list">
                    {safeRecentPositions.map((position, index) => (
                      <div key={index} className="position-item">
                        <strong>{position.title || 'Unknown'}</strong> at {position.company || 'Unknown'}
                        {position.duration && <span> • {position.duration}</span>}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Education Analysis */}
              <div className="breakdown-category">
                <h4>Education</h4>
                <p>
                  <strong>{result.ats_breakdown?.education_analysis?.degree_count || 0}</strong> degrees found
                </p>
                {result.ats_breakdown?.education_analysis?.highest_degree && (
                  <p>Highest: {result.ats_breakdown.education_analysis.highest_degree}</p>
                )}
                {safeInstitutions.length > 0 && (
                  <div className="institutions-list">
                    {safeInstitutions.map((institution, index) => (
                      <span key={index} className="institution-tag">
                        {institution}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* AI Recommendations */}
            {result.ai_recommendations_available && (
              <div className="ai-recommendations">
                <div className="ai-icon">🤖</div>
                <div className="ai-content">
                  <h3>AI Optimization Recommendations</h3>
                  <p>Download the full analysis report for detailed AI-powered optimization suggestions to improve your ATS score.</p>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="action-buttons">
              {result.analysis_report_url && (
                <button onClick={downloadAnalysisReport} className="download-btn">
                  <span className="btn-icon">📊</span>
                  Download Full Analysis Report
                </button>
              )}
              <button onClick={resetForm} className="new-resume-btn">
                <span className="btn-icon">🔄</span>
                Analyze Another Resume
              </button>
            </div>
          </div>
        )}

        <footer className="footer">
          <p>Powered by Affinda API & Gemini AI • Professional ATS Scoring • Secure Processing</p>
        </footer>
      </div>
    </div>
  );
};

export default ResumeOptimizer;