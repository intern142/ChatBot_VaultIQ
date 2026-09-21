import { useState } from 'react';

export default function Documents() {
  const [question, setQuestion] = useState('');
  const [questions, setQuestions] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');

  const recentDocuments = [];
  const allDocuments = [];

  const handleAsk = (e) => {
    e.preventDefault();
    if (!question.trim()) return;
    setQuestions([
      ...questions,
      { q: question, askedAt: new Date().toLocaleTimeString(), answered: false },
    ]);
    setQuestion('');
  };

  const filteredDocs = allDocuments.filter((doc) =>
    doc.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="page">
      <h1>Documents Upload</h1>
      <p className="page-placeholder">
        Upload, search, and manage your organization's documents.
      </p>

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

      <h2 className="section-title recent-title">Upload Document</h2>
      <div className="upload-box">
        <input type="file" className="file-input" />
        <p className="upload-hint">PDF, DOCX, TXT — max 20MB</p>
        <button className="primary-btn">Upload Document</button>
      </div>

      <h2 className="section-title recent-title">Search Documents</h2>
      <div className="search-bar">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search documents by name..."
        />
        <button type="button">Search</button>
      </div>

      <h2 className="section-title recent-title">Recently Uploaded Documents</h2>
      {recentDocuments.length === 0 ? (
        <div className="empty-state">
          <p>No documents uploaded yet.</p>
        </div>
      ) : (
        <div className="document-list">
          {recentDocuments.map((doc, i) => (
            <div className="document-item" key={i}>
              <span>{doc.name}</span>
              <span className="doc-time">{doc.uploadedAt}</span>
            </div>
          ))}
        </div>
      )}

      <h2 className="section-title recent-title">All Documents</h2>
      {filteredDocs.length === 0 ? (
        <div className="empty-state">
          <p>No documents found.</p>
        </div>
      ) : (
        <div className="document-list">
          {filteredDocs.map((doc, i) => (
            <div className="document-item" key={i}>
              <span>{doc.name}</span>
              <span className="doc-time">{doc.uploadedAt}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
