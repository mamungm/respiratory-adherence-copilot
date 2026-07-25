const BASE = "/api";

export async function fetchPatients() {
  const res = await fetch(`${BASE}/patients`);
  if (!res.ok) throw new Error("Failed to fetch patients");
  return res.json();
}

export async function sendChatMessage(message) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error("Chat request failed");
  return res.json();
}
