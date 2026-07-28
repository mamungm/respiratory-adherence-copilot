import { pool } from "../db.js";
import { embed } from "../rag/embeddings.js";

const DEFAULT_K = 4;

/**
 * Embeds the query and returns the closest document chunks by cosine
 * similarity. pgvector's <=> operator is cosine *distance*; embeddings.js
 * normalizes vectors, so 1 - distance is a clean 0-1 similarity score.
 */
export async function searchDeviceDocs(query, k = DEFAULT_K) {
  const queryEmbedding = await embed(query);
  const vectorLiteral = `[${queryEmbedding.join(",")}]`;
  const limit = Number.isInteger(k) && k > 0 ? Math.min(k, 10) : DEFAULT_K;

  const { rows } = await pool.query(
    `SELECT source, chunk_index, content,
            1 - (embedding <=> $1::vector) AS similarity
     FROM document_chunks
     ORDER BY embedding <=> $1::vector
     LIMIT $2`,
    [vectorLiteral, limit]
  );

  return rows.map((r) => ({
    source: r.source,
    chunk_index: r.chunk_index,
    similarity: Number(Number(r.similarity).toFixed(4)),
    content: r.content,
  }));
}

export const docSearchToolDefinition = {
  name: "search_device_docs",
  description:
    "Search device instructions-for-use (AeroChamber, Aerobika, AeroEclipse) and " +
    "general inhaler-technique/adherence guidance for passages relevant to a " +
    "natural-language question. Use this for questions about how a device works, " +
    "cleaning/maintenance, technique, or clinical guidance - not for questions about " +
    "a specific patient's data (use query_adherence_db for that). Returns the most " +
    "relevant passages with their source document, most similar first.",
  input_schema: {
    type: "object",
    properties: {
      query: { type: "string", description: "Natural-language question to search for." },
      k: {
        type: "integer",
        description: "Number of passages to return (default 4, max 10).",
      },
    },
    required: ["query"],
  },
};
