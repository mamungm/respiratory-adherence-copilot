import pg from "pg";
import "dotenv/config";

const { Pool } = pg;

// Pool reads DATABASE_URL if set; otherwise falls back to this default,
// which matches docker-compose.yml for local dev.
export const pool = new Pool({
  connectionString:
    process.env.DATABASE_URL || "postgresql://postgres:postgres@localhost:5432/adherence",
});

pool.on("error", (err) => {
  console.error("Unexpected Postgres pool error", err);
});
