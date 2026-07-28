import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { sendChatMessage } from "../api.js";

export default function ChatWidget() {
  const [messages, setMessages] = useState([
    { role: "assistant", text: 'Ask me about patient adherence, e.g. "Which patients are high risk?"' },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const logRef = useRef(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend() {
    if (!input.trim() || loading) return;
    const userMessage = { role: "user", text: input };
    setMessages((m) => [...m, userMessage]);
    setInput("");
    setLoading(true);
    try {
      const { reply } = await sendChatMessage(userMessage.text);
      setMessages((m) => [...m, { role: "assistant", text: reply }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", text: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="chat-widget">
      <h2>Ask the Copilot</h2>
      <div className="chat-log" ref={logRef}>
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble-row chat-bubble-row-${m.role}`}>
            <div className={`chat-bubble chat-bubble-${m.role}`}>
              <span className="chat-role-label">{m.role === "user" ? "You" : "Copilot"}</span>
              {m.role === "assistant" ? (
                <div className="chat-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                </div>
              ) : (
                <p className="chat-plain">{m.text}</p>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-bubble-row chat-bubble-row-assistant">
            <div className="chat-bubble chat-bubble-assistant chat-typing">
              <span className="chat-role-label">Copilot</span>
              <p className="chat-plain">Thinking…</p>
            </div>
          </div>
        )}
      </div>
      <div className="chat-input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Which patients are at risk this week?"
          disabled={loading}
        />
        <button onClick={handleSend} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </section>
  );
}
