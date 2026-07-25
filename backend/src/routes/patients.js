import { Router } from "express";
import { pool } from "../db.js";

const router = Router();

// GET /api/patients - list all patients with their latest adherence + risk score
router.get("/", async (req, res) => {
  try {
    const { rows } = await pool.query(
      `SELECT p.patient_id, p.device_type, f.adherence_rate, f.missed_dose_max_streak,
              f.technique_error_rate, s.risk_score, s.risk_tier
       FROM patients p
       LEFT JOIN patient_features f ON f.patient_id = p.patient_id
       LEFT JOIN adherence_scores s ON s.patient_id = p.patient_id
       ORDER BY s.risk_score DESC NULLS LAST`
    );
    res.json(rows);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to fetch patients" });
  }
});

// GET /api/patients/:id - single patient detail + dose history
router.get("/:id", async (req, res) => {
  try {
    const { rows: patientRows } = await pool.query(
      `SELECT * FROM patients WHERE patient_id = $1`,
      [req.params.id]
    );
    const patient = patientRows[0];
    if (!patient) return res.status(404).json({ error: "Patient not found" });

    const { rows: featureRows } = await pool.query(
      `SELECT * FROM patient_features WHERE patient_id = $1`,
      [req.params.id]
    );
    const { rows: scoreRows } = await pool.query(
      `SELECT * FROM adherence_scores WHERE patient_id = $1`,
      [req.params.id]
    );
    const { rows: events } = await pool.query(
      `SELECT expected_time, event_timestamp, dose_completed, technique_error
       FROM dose_events WHERE patient_id = $1 ORDER BY expected_time`,
      [req.params.id]
    );

    res.json({
      patient,
      features: featureRows[0] ?? null,
      score: scoreRows[0] ?? null,
      events,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Failed to fetch patient" });
  }
});

export default router;
