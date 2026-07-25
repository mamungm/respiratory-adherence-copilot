import Dashboard from "./components/Dashboard.jsx";
import ChatWidget from "./components/ChatWidget.jsx";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Respiratory Adherence Copilot</h1>
        <p>AeroChamber · Aerobika · AeroEclipse patient monitoring (demo data)</p>
      </header>
      <main className="app-main">
        <Dashboard />
        <ChatWidget />
      </main>
    </div>
  );
}
