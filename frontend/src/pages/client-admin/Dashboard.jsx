import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('dashboard');
  const [question, setQuestion] = useState('');
  const [questions, setQuestions] = useState([]);

  const tabs = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'upload', label: 'Document Upload' },
    { id: 'search', label: 'Ask Question' },
    { id: 'profile', label: 'Profile' },
  ];

  const handleAsk = (e) => {
    e.preventDefault();
    if (!question.trim()) return;
    setQuestions([
      ...questions,
      { q: question, askedAt: new Date().toLocaleTimeString(), answered: false },
    ]);
    setQuestion('');
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="page">
      <div className="dashboard-header">
        <h1 className="dashboard-title">Welcome, {user?.name || 'User'}</h1>
        <button className="logout-btn light" onClick={handleLogout}>
          Logout
        </button>
      </div>

      <div className="dashboard-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="dashboard-content">
        {activeTab === 'dashboard' && (
          <div>
            <h2 className="section-title">Overview</h2>
            <div className="stats-grid">
              <div className="stat-card">
                <h3>Total Employees</h3>
                <p className="stat-value">0</p>
              </div>
              <div className="stat-card">
                <h3>Active Employees</h3>
                <p className="stat-value">0</p>
              </div>
              <div className="stat-card">
                <h3>Pending Invitations</h3>
                <p className="stat-value">0</p>
              </div>
              <div className="stat-card">
                <h3>Total Documents</h3>
                <p className="stat-value">0</p>
              </div>
              <div className="stat-card">
                <h3>Documents Pending Approval</h3>
                <p className="stat-value">0</p>
              </div>
              <div className="stat-card">
                <h3>Documents Processing</h3>
                <p className="stat-value">0</p>
              </div>
            </div>

            <h2 className="section-title recent-title">Recently Added Documents</h2>
            <div className="empty-state">
              <p>No documents added yet.</p>
              <button className="primary-btn" onClick={() => setActiveTab('upload')}>
                Upload your first document
              </button>
            </div>
          </div>
        )}

        {activeTab === 'upload' && (
          <div>
            <h2 className="section-title">Document Upload</h2>
            <p className="page-placeholder">
              Upload policies, HR rules, SOPs for your organization.
            </p>
            <div className="upload-box">
              <input type="file" className="file-input" />
              <p className="upload-hint">PDF, DOCX, TXT — max 20MB</p>
              <button className="primary-btn">Upload Document</button>
            </div>
          </div>
        )}

        {activeTab === 'search' && (
          <div>
            <h2 className="section-title">Ask a Question</h2>
            <p className="page-placeholder">
              Ask in plain language. VaultIQ searches only your organization's approved documents.
            </p>
            <form className="search-bar" onSubmit={handleAsk}>
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g. What is the leave policy for new employees?"
              />
              <button type="submit">Ask</button>
            </form>

            {questions.length > 0 && (
              <div className="question-list">
                {questions.map((item, i) => (
                  <div className="question-item" key={i}>
                    <div className="q-head">
                      <span className="q-text">{item.q}</span>
                      <span className="q-time">{item.askedAt}</span>
                    </div>
                    <p className="q-status pending">
                      Awaiting backend response (demo)
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'profile' && (
          <div>
            <h2 className="section-title">Profile</h2>
            <div className="profile-card">
              <div className="form-group">
                <label>Name</label>
                <input type="text" value={user?.name || ''} readOnly />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input type="text" value={user?.email || ''} readOnly />
              </div>
              <div className="form-group">
                <label>Organization</label>
                <input type="text" value={user?.organization || ''} readOnly />
              </div>
              <div className="form-group">
                <label>Role</label>
                <input type="text" value={user?.role || ''} readOnly />
              </div>
              <button className="primary-btn" onClick={handleLogout}>
                Logout
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}