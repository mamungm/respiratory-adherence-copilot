import { useState } from "react";
import { sendChatMessage } from "../api.js";

export default function ChatWidget() {
  const [messages, setMessages] = useState([
    { role: "assistant", text: 'Ask me about patient adherence, e.g. "Which patients are high risk?"' },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSend() {
    if (!input.trim()) return;
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
      <div className="chat-log">
        {messages.map((m, i) => (
          <p key={i} className={`chat-msg chat-${m.role}`}>
            <strong>{m.role === "user" ? "You" : "Copilot"}:</strong> {m.text}
          </p>
        ))}
        {loading && <p className="chat-msg chat-assistant">Copilot is thinking…</p>}
      </div>
      <div className="chat-input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Which patients are at risk this week?"
        />
        <button onClick={handleSend} disabled={loading}>
          Send
        </button>
      </div>
    </section>
  );
}
