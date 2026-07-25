import Database from "better-sqlite3";
import path from "node:path";
import { fileURLToPath } from "node:url";
import "dotenv/config";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const dbPath = path.resolve(__dirname, process.env.DB_PATH || "../../data/adherence.db");

// fileMustExist: run the Python ETL pipeline first (see README) so this
// file exists before the API starts.
export const db = new Database(dbPath, { readonly: false, fileMustExist: true });
db.pragma("journal_mode = WAL");
