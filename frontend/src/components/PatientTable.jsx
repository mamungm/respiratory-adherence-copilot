const TIER_CLASS = {
  High: "tier-high",
  Medium: "tier-medium",
  Low: "tier-low",
};

export default function PatientTable({ patients }) {
  if (!patients.length) {
    return <p>No patient data yet — run the ETL pipeline first (see README).</p>;
  }

  return (
    <table className="patient-table">
      <thead>
        <tr>
          <th>Patient</th>
          <th>Device</th>
          <th>Adherence</th>
          <th>Longest Missed Streak</th>
          <th>Technique Error Rate</th>
          <th>Risk</th>
        </tr>
      </thead>
      <tbody>
        {patients.map((p) => (
          <tr key={p.patient_id}>
            <td>{p.patient_id}</td>
            <td>{p.device_type}</td>
            <td>{(p.adherence_rate * 100).toFixed(0)}%</td>
            <td>{p.missed_dose_max_streak} days</td>
            <td>{(p.technique_error_rate * 100).toFixed(0)}%</td>
            <td>
              <span className={`tier-badge ${TIER_CLASS[p.risk_tier] ?? ""}`}>
                {p.risk_tier ?? "—"} ({p.risk_score ?? "—"})
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
