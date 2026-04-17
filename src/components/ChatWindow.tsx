"use client";

import { useState } from "react";
import { Header } from "./Header";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { QuickActions } from "./QuickActions";
import type { Message } from "@/lib/types";

const WELCOME_MESSAGE: Message = {
  role: "assistant",
  content:
    "Hi! I'm **AirBot**, your Airpay PoS support assistant. I can help with:\n\n- Device onboarding and activation\n- Payments, QR codes, and settlements\n- API and SDK integrations\n- Troubleshooting errors and hardware issues\n- Chargebacks, refunds, and card problems\n- Transaction history and reconciliation\n\nWhat can I help you with today?",
};

export function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [isLoading, setIsLoading] = useState(false);

  async function sendMessage(text: string) {
    const userMsg: Message = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setIsLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: newMessages.filter((m) => m !== WELCOME_MESSAGE) }),
      });

      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const data = (await res.json()) as Message;
      setMessages((prev) => [...prev, data]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Sorry, I hit an issue reaching the support service. Please try again in a moment, or contact Airpay Support at 1800-102-2255.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function reset() {
    setMessages([WELCOME_MESSAGE]);
  }

  const showQuickActions = messages.length <= 1 && !isLoading;

  return (
    <div className="flex h-full w-full flex-col overflow-hidden rounded-none bg-white shadow-xl md:h-[92vh] md:max-w-2xl md:rounded-2xl">
      <Header onReset={reset} />
      <MessageList messages={messages} isLoading={isLoading} />
      {showQuickActions && <QuickActions onSelect={sendMessage} />}
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
