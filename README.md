# Airpay PoS Support Chatbot

AI-powered support chatbot for Airpay PoS (Point of Sale) machines. Built with Next.js 16 and the Claude API (`claude-opus-4-7`).

## Features

- **Conversational support** for all Airpay PoS domains:
  - Onboarding (merchant registration, KYC, device activation, account setup)
  - Merchant solutions (payment methods, QR codes, settlements, reports)
  - Integrations (REST API, SDKs, plugins, sandbox)
  - Troubleshooting (error codes, connectivity, software, hardware)
  - Card resolutions (refunds, chargebacks, declined transactions)
  - Transactions (history, reconciliation, settlements, void vs refund)
- **Rich markdown responses** with step-by-step procedures, bullet lists, and inline error codes
- **Quick action buttons** for common queries
- **Prompt caching** on the system prompt so the knowledge base is served from cache after the first call
- **Responsive UI** (mobile full-screen, desktop centered card)

## Stack

- Next.js 16 (App Router, TypeScript)
- Tailwind CSS v4
- Anthropic Claude API (`@anthropic-ai/sdk`), model `claude-opus-4-7`
- `react-markdown`

## Getting Started

1. **Install**
   ```bash
   npm install
   ```

2. **Configure**
   ```bash
   cp .env.example .env.local
   # set ANTHROPIC_API_KEY in .env.local
   ```

3. **Run**
   ```bash
   npm run dev
   ```
   Open http://localhost:3000.

## Project Structure

```
src/
├── app/
│   ├── api/chat/route.ts    # POST endpoint → Claude
│   ├── layout.tsx
│   ├── page.tsx
│   └── globals.css
├── components/              # Chat UI
│   ├── ChatWindow.tsx       # State owner
│   ├── Header.tsx
│   ├── MessageList.tsx
│   ├── MessageBubble.tsx
│   ├── ChatInput.tsx
│   ├── QuickActions.tsx
│   └── TypingIndicator.tsx
├── lib/
│   ├── types.ts
│   ├── claude.ts            # Anthropic SDK wrapper
│   └── systemPrompt.ts      # Builds system prompt from knowledge base
└── data/
    └── knowledgeBase.ts     # Structured Airpay PoS knowledge (6 domains)
```

## Extending the Knowledge Base

Edit `src/data/knowledgeBase.ts`. Each domain has entries with `topic`, `description`, and optional `steps`, `commonIssues`, and `notes`. `src/lib/systemPrompt.ts` serializes everything into XML-tagged sections the model consumes.

## API

`POST /api/chat`

Request:
```json
{
  "messages": [
    { "role": "user", "content": "How do I activate my PoS device?" }
  ]
}
```

Response:
```json
{ "role": "assistant", "content": "..." }
```
