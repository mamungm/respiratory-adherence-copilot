import { runReadOnlyQuery, sqlToolDefinition } from "../tools/sqlTool.js";
import { searchDeviceDocs, docSearchToolDefinition } from "../tools/docSearchTool.js";
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

const SYSTEM_PROMPT = `You are a clinical adherence assistant for Trudell Medical's
respiratory devices (AeroChamber, Aerobika, AeroEclipse). You have two tools:

- query_adherence_db: structured patient data (adherence rate, missed-dose
  streaks, technique-error rate, risk scores). Use this for questions about
  specific patients or the cohort.
- search_device_docs: device instructions-for-use and clinical inhaler
  technique/adherence guidance. Use this for questions about how a device
  works, cleaning, technique errors, or general clinical guidance.

Use both together when it helps - e.g. for "why is patient P007 high risk
and what should we do about it", look up their features first, then search
guidance for the specific risk driver you found (e.g. high technique-error
rate). Be concise, cite specific patient IDs/numbers from query_adherence_db
and the source document from search_device_docs, and never fabricate a
value or claim you haven't retrieved from a tool.`;

const TOOLS = [sqlToolDefinition, docSearchToolDefinition];

const TOOL_HANDLERS = {
  query_adherence_db: (input) => runReadOnlyQuery(input.sql),
  search_device_docs: (input) => searchDeviceDocs(input.query, input.k),
};

const MODEL = "claude-sonnet-5";
const MAX_TOOL_ROUNDS = 4; // guard against runaway tool-use loops

async function runTool(toolUse) {
  try {
    const handler = TOOL_HANDLERS[toolUse.name];
    if (!handler) throw new Error(`Unknown tool: ${toolUse.name}`);
    return await handler(toolUse.input);
  } catch (err) {
    return { error: err.message };
  }
}

async function chat(message, res) {
  try {
    const messages = [{ role: "user", content: message }];

    let response = await anthropic.messages.create({
      model: MODEL,
      max_tokens: 1024,
      system: SYSTEM_PROMPT,
      tools: TOOLS,
      messages,
    });

    let rounds = 0;
    while (response.stop_reason === "tool_use" && rounds < MAX_TOOL_ROUNDS) {
      rounds += 1;
      // Claude can request more than one tool in a single turn (e.g. SQL
      // lookup + doc search together) - run all of them, not just the first.
      const toolUses = response.content.filter((c) => c.type === "tool_use");

      const toolResultBlocks = await Promise.all(
        toolUses.map(async (toolUse) => ({
          type: "tool_result",
          tool_use_id: toolUse.id,
          content: JSON.stringify(await runTool(toolUse)),
        }))
      );

      messages.push({ role: "assistant", content: response.content });
      messages.push({ role: "user", content: toolResultBlocks });

      response = await anthropic.messages.create({
        model: MODEL,
        max_tokens: 1024,
        system: SYSTEM_PROMPT,
        tools: TOOLS,
        messages,
      });
    }

    const textBlock = response.content.find((c) => c.type === "text");
    res.json({ reply: textBlock?.text ?? "" });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Chat request failed" });
  }
}

export default chat;
