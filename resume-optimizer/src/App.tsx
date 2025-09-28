// ResumeOptimizer.tsx
import React, { useState, useRef } from 'react';
import './ResumeOptimizer.css';

interface ResumeScore {
  score: number;
  sections_found?: string[];
  word_count?: number;
  has_contact_info?: boolean;
  note?: string; // Scoring source
}

interface OptimizationResponse {
  before_score: number;
  after_score: number;
  score_improvement: number;
  before_details: ResumeScore;
  after_details: ResumeScore;
  enhanced_resume_url: string;
  text_extracted: boolean;
  text_length: number;
}

const ResumeOptimizer: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState('');
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [result, setResult] = useState<OptimizationResponse | null>(null);
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fix: Browser-friendly interval ref
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

  const handleOptimize = async () => {
    if (!file) {
      setError('Please select a PDF file');
      return;
    }

    setIsOptimizing(true);
    setError('');
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (jobDescription) formData.append('job_description', jobDescription);

      // Browser-friendly interval for upload progress simulation
      progressIntervalRef.current = window.setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
            return 90;
          }
          return prev + 10;
        });
      }, 500);

      const response = await fetch('http://127.0.0.1:8000/optimize_resume/', {
        method: 'POST',
        body: formData,
      });

      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      setUploadProgress(100);

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Optimization failed');
      }

      const data: OptimizationResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsOptimizing(false);
      setUploadProgress(0);
    }
  };

  const downloadEnhancedResume = () => {
    if (result?.enhanced_resume_url) {
      window.open(`http://127.0.0.1:8000${result.enhanced_resume_url}`, '_blank');
    }
  };

  const resetForm = () => {
    setFile(null);
    setJobDescription('');
    setResult(null);
    setError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#f59e0b';
    return '#ef4444';
  };

  const getScoreMessage = (score: number) => {
    if (score >= 80) return 'Excellent!';
    if (score >= 60) return 'Good, but can be improved';
    return 'Needs significant improvement';
  };

  return (
    <div className="resume-optimizer">
      <div className="container">
        <header className="header">
          <h1>AI Resume ATS Optimizer</h1>
          <p>Upload your resume to get an ATS score and AI-powered optimization</p>
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
                    <button type="button" className="change-file-btn" onClick={() => fileInputRef.current?.click()}>Change File</button>
                  </>
                ) : (
                  <>
                    <h3>Drag & Drop your resume</h3>
                    <p>or</p>
                    <label htmlFor="file-upload" className="browse-btn">Browse Files</label>
                    <p className="file-requirements">PDF files only, max 10MB</p>
                  </>
                )}
              </div>
            </div>

            <div className="job-description-section">
              <label htmlFor="job-description" className="section-label">Job Description (Optional)</label>
              <textarea
                id="job-description"
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Paste the job description here for targeted optimization..."
                rows={4}
              />
            </div>

            {error && <div className="error-message">⚠️ {error}</div>}

            <button onClick={handleOptimize} disabled={!file || isOptimizing} className="optimize-btn">
              {isOptimizing ? 'Optimizing...' : 'Optimize Resume'}
            </button>

            {isOptimizing && (
              <div className="progress-section">
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
                </div>
                <p>Analyzing and optimizing your resume...</p>
              </div>
            )}
          </div>
        ) : (
          <div className="results-section">
            <div className="score-comparison">
              <div className="score-card before-score">
                <h3>Before Optimization</h3>
                <div className="score-circle" style={{ borderColor: getScoreColor(result.before_score) }}>
                  <span className="score-value">{result.before_score}</span>
                  <span className="score-label">ATS Score</span>
                </div>
                <p className="score-message">{getScoreMessage(result.before_score)}</p>
                <p className="score-source">Scored via: {result.before_details.note}</p>
              </div>

              <div className="improvement-arrow">→</div>

              <div className="score-card after-score">
                <h3>After Optimization</h3>
                <div className="score-circle" style={{ borderColor: getScoreColor(result.after_score) }}>
                  <span className="score-value">{result.after_score}</span>
                  <span className="score-label">ATS Score</span>
                </div>
                <p className="score-message">{getScoreMessage(result.after_score)}</p>
                <p className="score-source">Scored via: {result.after_details.note}</p>
              </div>
            </div>

            <div className="improvement-stats">
              <div className="stat-item">
                <span className="stat-value" style={{ color: result.score_improvement >= 0 ? '#10b981' : '#ef4444' }}>
                  {result.score_improvement >= 0 ? '+' : ''}{result.score_improvement}
                </span>
                <span className="stat-label">Score Improvement</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{result.before_details.word_count || 'N/A'}</span>
                <span className="stat-label">Words (Before)</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{result.text_length}</span>
                <span className="stat-label">Characters Extracted</span>
              </div>
            </div>

            <div className="details-section">
              <div className="details-grid">
                <div className="detail-item">
                  <h4>Sections Found</h4>
                  <div className="sections-list">
                    {(result.before_details.sections_found || []).map((section, index) => (
                      <span key={index} className="section-tag">{section}</span>
                    ))}
                  </div>
                </div>
                <div className="detail-item">
                  <h4>Contact Info</h4>
                  <span className={`status ${result.before_details.has_contact_info ? 'present' : 'missing'}`}>
                    {result.before_details.has_contact_info ? '✓ Present' : '✗ Missing'}
                  </span>
                </div>
                <div className="detail-item">
                  <h4>Optimization Note</h4>
                  <p>{result.after_details.note || 'Enhanced with AI optimization'}</p>
                </div>
              </div>
            </div>

            <div className="action-buttons">
              <button onClick={downloadEnhancedResume} className="download-btn">📥 Download Enhanced Resume</button>
              <button onClick={resetForm} className="new-resume-btn">🔄 Optimize Another Resume</button>
            </div>
          </div>
        )}

        <footer className="footer">
          <p>Powered by AI • Secure PDF processing • ATS-optimized results</p>
        </footer>
      </div>
    </div>
  );
};

export default ResumeOptimizer;
