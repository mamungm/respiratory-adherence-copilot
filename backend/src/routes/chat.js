import { Router } from "express";
import chat from "../services/chatService.js";

const router = Router();

// POST /api/chat  { message: string }
router.post("/", async (req, res) => {
  const { message } = req.body;
  if (!message) return res.status(400).json({ error: "message is required" });

  await chat(message, res);
});

export default router;
