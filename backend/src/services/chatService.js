import {runReadOnlyQuery, sqlToolDefinition} from "../tools/sqlTool.js";
import Anthropic from "@anthropic-ai/sdk";

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

const SYSTEM_PROMPT = `You are a clinical adherence assistant for Trudell Medical's
respiratory devices (AeroChamber, Aerobika, AeroEclipse). Answer the clinician's
questions using the query_adherence_db tool to look up real data. Be concise,
cite specific patient IDs and numbers, and never fabricate values you haven't
retrieved from the tool.`;

const MODEL = "claude-sonnet-5";
const MAX_TOOL_ROUNDS = 4; // guard against runaway tool-use loops

async function chat(message, res) {
    try {
        const messages = [{role: "user", content: message}];

        let response = await anthropic.messages.create({
            model: MODEL,
            max_tokens: 1024,
            system: SYSTEM_PROMPT,
            tools: [sqlToolDefinition],
            messages,
        });

        let rounds = 0;
        while (response.stop_reason === "tool_use" && rounds < MAX_TOOL_ROUNDS) {
            rounds += 1;
            const toolUse = response.content.find((c) => c.type === "tool_use");

            let toolResult;
            try {
                toolResult = await runReadOnlyQuery(toolUse.input.sql);
            } catch (err) {
                toolResult = {error: err.message};
            }

            messages.push({role: "assistant", content: response.content});
            messages.push({
                role: "user",
                content: [
                    {
                        type: "tool_result",
                        tool_use_id: toolUse.id,
                        content: JSON.stringify(toolResult),
                    },
                ],
            });

            response = await anthropic.messages.create({
                model: MODEL,
                max_tokens: 1024,
                system: SYSTEM_PROMPT,
                tools: [sqlToolDefinition],
                messages,
            });
        }

        const textBlock = response.content.find((c) => c.type === "text");
        res.json({reply: textBlock?.text ?? ""});
    } catch (err) {
        console.error(err);
        res.status(500).json({error: "Chat request failed"});
    }
}

export default chat;