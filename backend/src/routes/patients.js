import { Router } from "express";
import { db } from "../db.js";

const router = Router();

// GET /api/patients - list all patients with their latest adherence + risk score
router.get("/", (req, res) => {
  const rows = db
    .prepare(
      `SELECT p.patient_id, p.device_type, f.adherence_rate, f.missed_dose_max_streak,
              f.technique_error_rate, s.risk_score, s.risk_tier
       FROM patients p
       LEFT JOIN patient_features f ON f.patient_id = p.patient_id
       LEFT JOIN adherence_scores s ON s.patient_id = p.patient_id
       ORDER BY s.risk_score DESC`
    )
    .all();
  res.json(rows);
});

// GET /api/patients/:id - single patient detail + dose history
router.get("/:id", (req, res) => {
  const patient = db.prepare(`SELECT * FROM patients WHERE patient_id = ?`).get(req.params.id);
  if (!patient) return res.status(404).json({ error: "Patient not found" });

  const features = db
    .prepare(`SELECT * FROM patient_features WHERE patient_id = ?`)
    .get(req.params.id);
  const score = db.prepare(`SELECT * FROM adherence_scores WHERE patient_id = ?`).get(req.params.id);
  const events = db
    .prepare(
      `SELECT expected_time, event_timestamp, dose_completed, technique_error
       FROM dose_events WHERE patient_id = ? ORDER BY expected_time`
    )
    .all(req.params.id);

  res.json({ patient, features, score, events });
});

export default router;
