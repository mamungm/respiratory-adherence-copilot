import { pipeline, env } from "@xenova/transformers";

const MODEL_NAME = "Xenova/all-MiniLM-L6-v2"; // 384-dim, must match VECTOR(384) in db/schema.sql

// Default cache dir lives under node_modules, which is owned by root at
// build time (npm install runs before the Dockerfile switches to USER
// node) - point it at /tmp instead so the non-root runtime user can write
// the downloaded model files on first use. Override with
// TRANSFORMERS_CACHE_DIR if you want it to persist across container
// restarts (mount a volume there).
env.cacheDir = process.env.TRANSFORMERS_CACHE_DIR || "/tmp/xenova-cache";

// Loaded once and reused - the feature-extraction pipeline downloads and
// caches the ONNX model on first call (needs network access the first
// time; cached in env.cacheDir after that).
let extractorPromise;
function getExtractor() {
  if (!extractorPromise) {
    extractorPromise = pipeline("feature-extraction", MODEL_NAME);
  }
  return extractorPromise;
}

/**
 * Embeds text into a 384-dim, L2-normalized vector.
 *
 * Used by both backend/scripts/ingest_docs.js (document ingestion) and
 * backend/src/tools/docSearchTool.js (query-time search) - using this one
 * function for both keeps the embedding space consistent by construction,
 * rather than relying on two separate implementations producing "the same"
 * embeddings.
 */
export async function embed(text) {
  const extractor = await getExtractor();
  const output = await extractor(text, { pooling: "mean", normalize: true });
  return Array.from(output.data);
}
