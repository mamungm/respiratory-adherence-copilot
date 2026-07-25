import express from "express";
import cors from "cors";
import "dotenv/config";
import patientsRouter from "./routes/patients.js";
import chatRouter from "./routes/chat.js";

const app = express();
app.use(cors());
app.use(express.json());

app.get("/api/health", (req, res) => res.json({ status: "ok" }));
app.use("/api/patients", patientsRouter);
app.use("/api/chat", chatRouter);

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => console.log(`Adherence Copilot API listening on :${PORT}`));
