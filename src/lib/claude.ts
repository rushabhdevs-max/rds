import Anthropic from "@anthropic-ai/sdk";
import { systemPrompt } from "@/lib/systemPrompt";
import type { Message } from "@/lib/types";

const client = new Anthropic();

export async function getChatResponse(messages: Message[]): Promise<string> {
  const response = await client.messages.create({
    model: "claude-opus-4-7",
    max_tokens: 2048,
    system: [
      {
        type: "text",
        text: systemPrompt,
        cache_control: { type: "ephemeral" },
      },
    ],
    messages: messages.map((m) => ({ role: m.role, content: m.content })),
  });

  const textBlock = response.content.find((b) => b.type === "text");
  return textBlock && textBlock.type === "text" ? textBlock.text : "";
}
