export default function Chat() {
  return (
    <div className="page">
      <h1>Chat</h1>
      <p className="page-placeholder">Ask a question about your organization's documents.</p>
      <div className="chat-placeholder">
        <div className="chat-input-area">
          <input type="text" placeholder="Type your question here..." disabled />
          <button disabled>Send</button>
        </div>
      </div>
    </div>
  );
}
