import { useEffect, useState } from "react";
import { fetchPatients } from "../api.js";
import PatientTable from "./PatientTable.jsx";

export default function Dashboard() {
  const [patients, setPatients] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchPatients().then(setPatients).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">Error loading patients: {error}</p>;

  return (
    <section className="dashboard">
      <h2>Patient Adherence Overview</h2>
      <PatientTable patients={patients} />
    </section>
  );
}
