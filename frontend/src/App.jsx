import { useState, useRef, useEffect } from "react";
import "./App.css";

// The FastAPI backend endpoint
const API_URL = "http://localhost:8001/ask";

// Example questions shown as clickable chips
const EXAMPLES = [
  "Why was Acme Corp overbilled in May 2025?",
  "Which customer had the largest overbilling?",
  "How many customers were overbilled, and the average amount?",
  "How many support tickets are still open?",
];

function App() {
  const [messages, setMessages] = useState([]); // {role: 'user'|'agent', text: string}
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  // Auto-scroll to the newest message
  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages, loading]);

  async function sendQuestion(question) {
    const q = question.trim();
    if (!q || loading) return;

    // Add the user's message
    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      setMessages((m) => [...m, { role: "agent", text: data.answer }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "agent", text: "Something went wrong reaching the agent. Is the backend running?" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">CS</div>
          <div className="brand-name">Support Agent</div>
        </div>

        <div className="cap-label">Capabilities</div>
        <ul className="cap-list">
          <li><span className="dot" /> Billing lookups</li>
          <li><span className="dot" /> Analytics &amp; trends</li>
          <li><span className="dot" /> Account details</li>
          <li><span className="dot" /> Support tickets</li>
        </ul>

        <div className="sidebar-foot">
          Data Agent · MVP
        </div>
      </aside>

      {/* Main chat panel */}
      <main className="chat">
        <header className="chat-head">
          <span className="chat-title">Resolution Assistant</span>
          <span className="chat-sub">Ask about billing, invoices, and accounts</span>
        </header>

        <div className="messages" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="empty">
              <div className="empty-title">How can I help?</div>
              <div className="empty-sub">Ask a question, or try one of these:</div>
              <div className="chips">
                {EXAMPLES.map((ex, i) => (
                  <button key={i} className="chip" onClick={() => sendQuestion(ex)}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className="bubble">{m.text}</div>
            </div>
          ))}

          {loading && (
            <div className="msg agent">
              <div className="bubble thinking">
                <span className="d" /><span className="d" /><span className="d" />
              </div>
            </div>
          )}
        </div>

        <div className="composer">
          <input
            className="composer-input"
            value={input}
            placeholder="Ask a question…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendQuestion(input)}
            disabled={loading}
          />
          <button
            className="send"
            onClick={() => sendQuestion(input)}
            disabled={loading || !input.trim()}
            aria-label="Send"
          >
            ↑
          </button>
        </div>
      </main>
    </div>
  );
}

export default App;