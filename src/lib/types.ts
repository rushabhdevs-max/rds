export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  messages: Message[];
}

export interface ChatResponse {
  role: "assistant";
  content: string;
}

export interface KnowledgeEntry {
  topic: string;
  description: string;
  steps?: string[];
  commonIssues?: string[];
  notes?: string[];
}

export interface DomainKnowledge {
  domainName: string;
  description: string;
  entries: KnowledgeEntry[];
}

export type KnowledgeBase = Record<string, DomainKnowledge>;
