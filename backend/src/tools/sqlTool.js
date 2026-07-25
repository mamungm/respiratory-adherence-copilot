import { pool } from "../db.js";

const ALLOWED_TABLES = ["patients", "dose_events", "patient_features", "adherence_scores"];

/**
 * Runs a SELECT-only query against the adherence database. Used as a
 * Claude tool so the LLM can answer natural-language questions without
 * unrestricted database access (no INSERT/UPDATE/DELETE, no DDL, and no
 * stacking multiple statements in one call).
 */
export async function runReadOnlyQuery(sql) {
  const trimmed = sql.trim().replace(/;+\s*$/, "");

  if (trimmed.includes(";")) {
    throw new Error("Multiple statements are not allowed.");
  }
  if (!/^select\s/i.test(trimmed)) {
    throw new Error("Only SELECT statements are allowed.");
  }
  const mentionsKnownTable = ALLOWED_TABLES.some((t) => trimmed.toLowerCase().includes(t));
  if (!mentionsKnownTable) {
    throw new Error("Query must reference one of the known tables.");
  }

  const { rows } = await pool.query(trimmed);
  return rows;
}

export const sqlToolDefinition = {
  name: "query_adherence_db",
  description:
    "Run a read-only SQL SELECT query against the patient adherence Postgres database. " +
    "Tables: patients(patient_id, device_type, prescribed_doses_per_day, monitoring_start, monitoring_days), " +
    "patient_features(patient_id, adherence_rate, missed_dose_max_streak, dose_interval_variance, technique_error_rate), " +
    "adherence_scores(patient_id, risk_score, risk_tier). Only SELECT statements are permitted.",
  input_schema: {
    type: "object",
    properties: {
      sql: { type: "string", description: "A SELECT-only SQL query." },
    },
    required: ["sql"],
  },
};
