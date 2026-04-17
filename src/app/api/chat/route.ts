import { NextResponse } from "next/server";
import { getChatResponse } from "@/lib/claude";
import type { ChatRequest, ChatResponse, Message } from "@/lib/types";

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as ChatRequest;
    if (!body.messages || !Array.isArray(body.messages) || body.messages.length === 0) {
      return NextResponse.json({ error: "messages array is required" }, { status: 400 });
    }

    const messages: Message[] = body.messages
      .filter((m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
      .map((m) => ({ role: m.role, content: m.content.slice(0, 4000) }));

    if (messages.length === 0) {
      return NextResponse.json({ error: "no valid messages" }, { status: 400 });
    }

    const text = await getChatResponse(messages);
    const response: ChatResponse = { role: "assistant", content: text };
    return NextResponse.json(response);
  } catch (err) {
    console.error("[/api/chat] error:", err);
    return NextResponse.json(
      { error: "Something went wrong. Please try again." },
      { status: 500 },
    );
  }
}
