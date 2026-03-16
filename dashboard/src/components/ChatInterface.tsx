/**
 * Conversational AI Interface Component
 * Natural language query interface over the FinTech knowledge graph.
 */

import React, { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, Database } from "lucide-react";
import { api } from "../services/api";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  cypher?: string;
  sources?: string[];
  loading?: boolean;
}

const EXAMPLE_QUERIES = [
  "Which open-source tools could improve AML compliance?",
  "Show emerging fintech infrastructure projects.",
  "Which repos could disrupt payment processing?",
  "What technologies have high startup potential?",
  "Which repos are relevant to Basel III?",
];

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hello! I'm your FinTech OSINT intelligence assistant. Ask me anything about the open-source fintech ecosystem — emerging technologies, compliance implications, disruption signals, or startup opportunities.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [showCypher, setShowCypher] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: text,
    };

    const loadingMsg: Message = {
      id: `loading-${Date.now()}`,
      role: "assistant",
      content: "",
      loading: true,
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const history = messages
        .filter((m) => !m.loading)
        .map((m) => ({ role: m.role, content: m.content }));
      history.push({ role: "user", content: text });

      const resp = await api.post("/api/v1/chat", { messages: history });
      const { answer, cypher_query, sources } = resp.data;

      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                content: answer,
                loading: false,
                cypher: cypher_query,
                sources,
              }
            : m
        )
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingMsg.id
            ? {
                ...m,
                content: "Sorry, I encountered an error. Please try again.",
                loading: false,
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 p-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
          >
            {/* Avatar */}
            <div
              className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${
                msg.role === "assistant"
                  ? "bg-blue-600"
                  : "bg-gray-700"
              }`}
            >
              {msg.role === "assistant" ? (
                <Bot className="h-4 w-4 text-white" />
              ) : (
                <User className="h-4 w-4 text-gray-300" />
              )}
            </div>

            {/* Bubble */}
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-100"
              }`}
            >
              {msg.loading ? (
                <div className="flex items-center gap-2 text-gray-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analyzing the knowledge graph…
                </div>
              ) : (
                <>
                  <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-gray-700">
                      <p className="text-xs text-gray-400 mb-1">Sources:</p>
                      <div className="flex flex-wrap gap-1">
                        {msg.sources.map((s) => (
                          <span
                            key={s}
                            className="rounded bg-gray-700 px-2 py-0.5 text-xs text-blue-300"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Cypher toggle */}
                  {msg.cypher && (
                    <button
                      onClick={() =>
                        setShowCypher(showCypher === msg.id ? null : msg.id)
                      }
                      className="mt-2 flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300"
                    >
                      <Database className="h-3 w-3" />
                      {showCypher === msg.id ? "Hide" : "Show"} Cypher query
                    </button>
                  )}
                  {showCypher === msg.id && msg.cypher && (
                    <pre className="mt-2 rounded bg-gray-900 p-3 text-xs text-green-400 overflow-x-auto">
                      {msg.cypher}
                    </pre>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Example queries */}
      {messages.length <= 1 && (
        <div className="px-4 pb-2">
          <p className="mb-2 text-xs text-gray-500">Try asking:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                onClick={() => sendMessage(q)}
                className="rounded-full border border-gray-700 px-3 py-1 text-xs text-gray-300 hover:border-blue-500 hover:text-blue-300 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-gray-800 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
            placeholder="Ask about fintech technologies, regulations, or disruption signals…"
            disabled={isLoading}
            className="flex-1 rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading}
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
