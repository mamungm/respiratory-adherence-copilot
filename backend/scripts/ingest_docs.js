#!/usr/bin/env node
/**
 * Chunks and embeds the markdown docs in rag/docs/ and loads them into the
 * document_chunks table (pgvector). Uses the same embed() function as
 * query-time search (src/rag/embeddings.js) so the vector space matches
 * exactly - one implementation, used at both ingest and query time.
 *
 * Idempotent: truncates document_chunks before reloading, so re-running
 * after editing/adding docs is safe.
 *
 * Usage (from the backend/ directory):
 *   node scripts/ingest_docs.js
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import "dotenv/config";
import { pool } from "../src/db.js";
import { embed } from "../src/rag/embeddings.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DOCS_DIR = path.resolve(__dirname, "../../rag/docs");
const MAX_CHUNK_CHARS = 800;

/**
 * Splits markdown into header-bounded sections, then further splits any
 * section longer than MAX_CHUNK_CHARS on paragraph breaks, so each chunk
 * stays a coherent, citable passage instead of an arbitrary character cut.
 */
function chunkMarkdown(text) {
  const sections = text.split(/\n(?=#{1,3}\s)/);
  const chunks = [];

  for (const section of sections) {
    const paragraphs = section
      .split(/\n{2,}/)
      .map((p) => p.trim())
      .filter(Boolean);

    let buffer = "";
    for (const para of paragraphs) {
      const candidate = buffer ? `${buffer}\n\n${para}` : para;
      if (candidate.length > MAX_CHUNK_CHARS && buffer) {
        chunks.push(buffer.trim());
        buffer = para;
      } else {
        buffer = candidate;
      }
    }
    if (buffer) chunks.push(buffer.trim());
  }

  return chunks.filter((c) => c.length > 0);
}

async function main() {
  if (!fs.existsSync(DOCS_DIR)) {
    console.error(`Docs directory not found: ${DOCS_DIR}`);
    process.exit(1);
  }

  const files = fs.readdirSync(DOCS_DIR).filter((f) => f.endsWith(".md"));
  if (files.length === 0) {
    console.error(`No .md files found in ${DOCS_DIR}`);
    process.exit(1);
  }

  await pool.query("TRUNCATE TABLE document_chunks RESTART IDENTITY");

  let total = 0;
  for (const file of files) {
    const text = fs.readFileSync(path.join(DOCS_DIR, file), "utf-8");
    const chunks = chunkMarkdown(text);

    for (let i = 0; i < chunks.length; i++) {
      const embedding = await embed(chunks[i]);
      const vectorLiteral = `[${embedding.join(",")}]`;
      await pool.query(
        `INSERT INTO document_chunks (source, chunk_index, content, embedding)
         VALUES ($1, $2, $3, $4::vector)`,
        [file, i, chunks[i], vectorLiteral]
      );
      total += 1;
    }
    console.log(`${file}: ${chunks.length} chunks`);
  }

  console.log(`Ingested ${total} chunks total.`);
  await pool.end();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
