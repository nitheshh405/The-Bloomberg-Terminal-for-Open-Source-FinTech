import React, { useState } from "react";
import {
  BarChart2,
  Network,
  Shield,
  TrendingUp,
  MessageSquare,
  FileText,
  Zap,
  Globe,
  ChevronRight,
} from "lucide-react";

// ── Inline mock data (no API needed for preview) ─────────────────────────────

const MOCK_STATS = {
  total_repos: 47832,
  total_devs: 183441,
  total_techs: 2847,
  high_disruption_count: 312,
  startup_signal_count: 589,
  avg_innovation_score: 61.4,
};

const MOCK_REPOS = [
  { name: "stripe/openai-financial-agents", sector: "payments", stars: 8432, score: 94.2, disruption: 87.1 },
  { name: "finos/common-domain-model", sector: "capital-markets", stars: 3891, score: 91.7, disruption: 82.4 },
  { name: "jpmorgan/quant-research", sector: "trading", stars: 6210, score: 89.4, disruption: 79.8 },
  { name: "openfinance/psd2-gateway", sector: "digital-banking", stars: 2103, score: 87.3, disruption: 74.2 },
  { name: "chainalysis/react-cryptoaddress", sector: "aml-compliance", stars: 1847, score: 85.6, disruption: 71.3 },
  { name: "plaid/link-sdk", sector: "payments", stars: 4520, score: 84.9, disruption: 68.7 },
  { name: "bank-of-england/cbdc-platform", sector: "regtech", stars: 1204, score: 84.1, disruption: 85.3 },
  { name: "polygon-io/client-go", sector: "financial-data", stars: 3102, score: 82.7, disruption: 62.1 },
  { name: "algorand/go-algorand", sector: "blockchain-defi", stars: 2890, score: 81.9, disruption: 69.4 },
  { name: "apache/fineract", sector: "lending", stars: 2341, score: 80.8, disruption: 73.2 },
];

const MOCK_TECHS = [
  { name: "ISO 20022 Parsers", category: "messaging", repos: 312, growth: "+340%" },
  { name: "ZK-Proof Finance", category: "cryptography", repos: 187, growth: "+156%" },
  { name: "AI AML Screening", category: "compliance", repos: 143, growth: "+89%" },
  { name: "CBDC Infrastructure", category: "digital-money", repos: 67, growth: "+78%" },
  { name: "Real-Time Payments", category: "payments", repos: 234, growth: "+45%" },
  { name: "Open Banking APIs", category: "infrastructure", repos: 421, growth: "+38%" },
];

const MOCK_SECTORS = [
  { name: "Payments", count: 8432, color: "#4f8ef7" },
  { name: "Trading", count: 6210, color: "#f74f4f" },
  { name: "Risk Management", count: 5891, color: "#f7a24f" },
  { name: "AML / Fraud", count: 4832, color: "#9b4ff7" },
  { name: "RegTech", count: 3921, color: "#4ff7e6" },
  { name: "DeFi / Blockchain", count: 7102, color: "#f7e64f" },
  { name: "Lending", count: 3201, color: "#4ff78e" },
  { name: "Identity / KYC", count: 2891, color: "#f74fb0" },
];

const CHAT_EXAMPLES = [
  "Which open-source tools improve AML compliance?",
  "Show emerging fintech infrastructure projects.",
  "Which repos could disrupt payment processing?",
  "What technologies have high startup potential?",
];

// ── Score badge ───────────────────────────────────────────────────────────────

const ScoreBadge = ({ score, color = "blue" }: { score: number; color?: string }) => {
  const c =
    score >= 80
      ? "bg-green-900/50 text-green-300 border-green-700"
      : score >= 60
      ? "bg-blue-900/50 text-blue-300 border-blue-700"
      : "bg-gray-800 text-gray-400 border-gray-700";
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-xs font-mono ${c}`}>
      {score.toFixed(1)}
    </span>
  );
};

// ── Sidebar nav ───────────────────────────────────────────────────────────────

const NAV = [
  { id: "overview", label: "Overview", icon: BarChart2 },
  { id: "repositories", label: "Repositories", icon: TrendingUp },
  { id: "technologies", label: "Technologies", icon: Zap },
  { id: "graph", label: "Knowledge Graph", icon: Network },
  { id: "compliance", label: "Compliance Map", icon: Shield },
  { id: "reports", label: "Weekly Reports", icon: FileText },
  { id: "geo", label: "Geographic Map", icon: Globe },
  { id: "chat", label: "AI Assistant", icon: MessageSquare },
];

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [activeTab, setActiveTab] = useState("overview");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([
    {
      role: "assistant",
      text: "Hello! I'm your FinTech OSINT intelligence assistant. Ask me anything about the open-source fintech ecosystem — emerging technologies, compliance implications, disruption signals, or startup opportunities.",
    },
  ]);

  const handleChat = () => {
    if (!chatInput.trim()) return;
    setChatMessages((m) => [
      ...m,
      { role: "user", text: chatInput },
      {
        role: "assistant",
        text: `Analyzing the knowledge graph for: "${chatInput}"…\n\nBased on current data, here are the top findings related to your query. Connect the API backend (port 8000) to get live results from the Neo4j knowledge graph.`,
      },
    ]);
    setChatInput("");
  };

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className="flex w-56 flex-col border-r border-gray-800 bg-gray-900">
        {/* Logo */}
        <div className="flex items-center gap-2.5 border-b border-gray-800 px-4 py-4">
          <BarChart2 className="h-6 w-6 text-blue-400 shrink-0" />
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-white">FinTech OSINT</p>
            <p className="text-xs text-gray-500">Intelligence Platform</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3">
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex w-full items-center gap-2.5 px-4 py-2.5 text-sm transition-colors ${
                activeTab === id
                  ? "bg-blue-600/20 text-blue-300 border-r-2 border-blue-500"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        {/* Live badge */}
        <div className="border-t border-gray-800 px-4 py-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <span className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
            Live · Updated Mon 06:00 UTC
          </div>
        </div>
      </aside>

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto">
        {/* Overview */}
        {activeTab === "overview" && (
          <div className="p-6 space-y-6">
            <div>
              <h1 className="text-xl font-bold text-white">Platform Overview</h1>
              <p className="text-sm text-gray-400 mt-1">
                Week of March 10, 2026 · 47,832 repositories monitored
              </p>
            </div>

            {/* KPI Grid */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
              {[
                { label: "Repositories", value: "47,832", sub: "↑ 1,243 this week", color: "blue" },
                { label: "Developers", value: "183K", sub: "tracked", color: "orange" },
                { label: "Technologies", value: "2,847", sub: "distinct", color: "purple" },
                { label: "High Disruption", value: "312", sub: "score ≥ 70", color: "red" },
                { label: "Startup Signals", value: "589", sub: "score ≥ 65", color: "green" },
                { label: "Avg Innovation", value: "61.4", sub: "out of 100", color: "yellow" },
              ].map(({ label, value, sub, color }) => (
                <div
                  key={label}
                  className={`rounded-xl border p-4 space-y-1
                    ${color === "blue" ? "border-blue-800 bg-blue-900/20" : ""}
                    ${color === "orange" ? "border-orange-800 bg-orange-900/20" : ""}
                    ${color === "purple" ? "border-purple-800 bg-purple-900/20" : ""}
                    ${color === "red" ? "border-red-800 bg-red-900/20" : ""}
                    ${color === "green" ? "border-green-800 bg-green-900/20" : ""}
                    ${color === "yellow" ? "border-yellow-800 bg-yellow-900/20" : ""}
                  `}
                >
                  <p className="text-xs text-gray-400">{label}</p>
                  <p className="text-2xl font-bold text-white">{value}</p>
                  <p className="text-xs text-gray-500">{sub}</p>
                </div>
              ))}
            </div>

            {/* Two-col layout */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              {/* Top repos table */}
              <div className="lg:col-span-2 rounded-xl border border-gray-800 bg-gray-900 p-5">
                <h2 className="mb-4 text-base font-semibold text-white flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-blue-400" />
                  Top Innovation Repositories
                </h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-800 text-xs text-gray-500">
                        <th className="pb-2 text-left font-medium">Repository</th>
                        <th className="pb-2 text-left font-medium">Sector</th>
                        <th className="pb-2 text-right font-medium">Stars</th>
                        <th className="pb-2 text-right font-medium">Innovation</th>
                        <th className="pb-2 text-right font-medium">Disruption</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800/50">
                      {MOCK_REPOS.map((r) => (
                        <tr key={r.name} className="hover:bg-gray-800/30 transition-colors">
                          <td className="py-2.5 pr-4">
                            <span className="font-mono text-xs text-blue-300">{r.name}</span>
                          </td>
                          <td className="py-2.5 pr-4">
                            <span className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-300">
                              {r.sector}
                            </span>
                          </td>
                          <td className="py-2.5 text-right text-gray-300">
                            {r.stars.toLocaleString()}
                          </td>
                          <td className="py-2.5 text-right">
                            <ScoreBadge score={r.score} />
                          </td>
                          <td className="py-2.5 text-right">
                            <ScoreBadge score={r.disruption} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Sector distribution */}
              <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
                <h2 className="mb-4 text-base font-semibold text-white">Sector Distribution</h2>
                <div className="space-y-3">
                  {MOCK_SECTORS.map((s) => {
                    const pct = Math.round((s.count / 8432) * 100);
                    return (
                      <div key={s.name}>
                        <div className="mb-1 flex justify-between text-xs">
                          <span className="text-gray-300">{s.name}</span>
                          <span className="text-gray-500">{s.count.toLocaleString()}</span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-gray-800">
                          <div
                            className="h-1.5 rounded-full transition-all"
                            style={{ width: `${pct}%`, backgroundColor: s.color }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Technologies */}
            <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
              <h2 className="mb-4 text-base font-semibold text-white flex items-center gap-2">
                <Zap className="h-4 w-4 text-yellow-400" />
                Fastest Growing Technologies
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {MOCK_TECHS.map((t) => (
                  <div
                    key={t.name}
                    className="rounded-lg border border-gray-800 bg-gray-800/40 p-3 space-y-1"
                  >
                    <p className="text-xs font-medium text-white leading-tight">{t.name}</p>
                    <p className="text-xs text-gray-500">{t.category}</p>
                    <p className="text-xs font-mono text-green-400">{t.growth}</p>
                    <p className="text-xs text-gray-400">{t.repos} repos</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Repositories tab */}
        {activeTab === "repositories" && (
          <div className="p-6 space-y-4">
            <h1 className="text-xl font-bold text-white">Repository Intelligence</h1>
            <p className="text-sm text-gray-400">
              All 47,832 fintech repositories ranked by innovation score.
            </p>
            <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
              <div className="flex gap-3 mb-4">
                {["All Sectors", "Payments", "Trading", "AML/KYC", "DeFi", "RegTech"].map((f) => (
                  <button
                    key={f}
                    className="rounded-full border border-gray-700 px-3 py-1 text-xs text-gray-300 hover:border-blue-500 hover:text-blue-300 transition-colors first:border-blue-500 first:text-blue-300"
                  >
                    {f}
                  </button>
                ))}
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800 text-xs text-gray-500">
                    <th className="pb-2 text-left font-medium">#</th>
                    <th className="pb-2 text-left font-medium">Repository</th>
                    <th className="pb-2 text-left font-medium">Sector</th>
                    <th className="pb-2 text-right font-medium">Stars</th>
                    <th className="pb-2 text-right font-medium">Innovation</th>
                    <th className="pb-2 text-right font-medium">Disruption</th>
                    <th className="pb-2 text-right font-medium">Startup</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50">
                  {MOCK_REPOS.map((r, i) => (
                    <tr key={r.name} className="hover:bg-gray-800/30 transition-colors cursor-pointer">
                      <td className="py-2.5 pr-3 text-gray-600 text-xs">{i + 1}</td>
                      <td className="py-2.5 pr-4">
                        <span className="font-mono text-xs text-blue-300 hover:text-blue-200">
                          {r.name}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4">
                        <span className="rounded bg-gray-800 px-1.5 py-0.5 text-xs text-gray-300">
                          {r.sector}
                        </span>
                      </td>
                      <td className="py-2.5 text-right text-gray-300 text-xs">
                        {r.stars.toLocaleString()}
                      </td>
                      <td className="py-2.5 text-right"><ScoreBadge score={r.score} /></td>
                      <td className="py-2.5 text-right"><ScoreBadge score={r.disruption} /></td>
                      <td className="py-2.5 text-right"><ScoreBadge score={r.score - 12} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Knowledge Graph tab */}
        {activeTab === "graph" && (
          <div className="p-6 space-y-4">
            <h1 className="text-xl font-bold text-white">Knowledge Graph</h1>
            <p className="text-sm text-gray-400">
              Interactive force-directed graph of the FinTech ecosystem. Connect the API backend to explore live relationships.
            </p>
            <div className="rounded-xl border border-gray-800 bg-gray-900 p-6 h-[520px] flex items-center justify-center">
              <div className="text-center space-y-3">
                <Network className="h-16 w-16 text-blue-600/40 mx-auto" />
                <p className="text-gray-400 text-sm">
                  D3.js force-directed graph renders here when connected to Neo4j.
                </p>
                <div className="flex flex-wrap justify-center gap-3 mt-4">
                  {[
                    { label: "Repository", color: "#4f8ef7" },
                    { label: "Technology", color: "#f74f4f" },
                    { label: "Sector", color: "#9b4ff7" },
                    { label: "Regulation", color: "#f7e64f" },
                    { label: "Developer", color: "#f7a24f" },
                  ].map(({ label, color }) => (
                    <div key={label} className="flex items-center gap-1.5 text-xs text-gray-400">
                      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
                      {label}
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-600 mt-2">
                  200k+ nodes · 500k+ edges · Real-time filtering
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Compliance tab */}
        {activeTab === "compliance" && (
          <div className="p-6 space-y-4">
            <h1 className="text-xl font-bold text-white">Compliance & Regulatory Map</h1>
            <p className="text-sm text-gray-400">Repositories mapped to US financial regulations.</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                { reg: "BSA / AML", repos: 847, high: 312, color: "red" },
                { reg: "Dodd-Frank", repos: 423, high: 156, color: "orange" },
                { reg: "PCI-DSS", repos: 634, high: 201, color: "yellow" },
                { reg: "SOX", repos: 312, high: 89, color: "purple" },
                { reg: "GLBA", repos: 289, high: 78, color: "blue" },
                { reg: "Basel III", repos: 198, high: 54, color: "green" },
                { reg: "CFPB 1033", repos: 421, high: 134, color: "teal" },
                { reg: "Reg SCI", repos: 156, high: 43, color: "indigo" },
              ].map(({ reg, repos, high }) => (
                <div key={reg} className="rounded-xl border border-gray-800 bg-gray-900 p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-white">{reg}</span>
                    <Shield className="h-4 w-4 text-gray-600" />
                  </div>
                  <div className="text-2xl font-bold text-white">{repos}</div>
                  <p className="text-xs text-gray-500">repositories mapped</p>
                  <div className="flex items-center gap-1 text-xs text-red-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
                    {high} high-risk
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reports tab */}
        {activeTab === "reports" && (
          <div className="p-6 space-y-4">
            <h1 className="text-xl font-bold text-white">Weekly Intelligence Reports</h1>
            <p className="text-sm text-gray-400">Auto-generated every Monday at 06:00 UTC and committed to Git.</p>
            <div className="space-y-3">
              {[
                { date: "2026-03-10", repos: 1243, highlights: ["ISO 20022 surge +340%", "CBDC reference implementations", "AI AML tools critical mass"] },
                { date: "2026-03-03", repos: 1108, highlights: ["ZK-proof privacy boom", "FedNow adoption wave", "Open Banking CFPB alignment"] },
                { date: "2026-02-24", repos: 987, highlights: ["RegTech automation +22%", "DeFi institutional pivot", "Embedded finance expansion"] },
              ].map((r) => (
                <div key={r.date} className="rounded-xl border border-gray-800 bg-gray-900 p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="text-sm font-semibold text-white">
                        Weekly Intelligence — {r.date}
                      </h3>
                      <p className="text-xs text-gray-500 mt-0.5">{r.repos} new repositories ingested</p>
                    </div>
                    <button className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300">
                      View Report <ChevronRight className="h-3 w-3" />
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {r.highlights.map((h) => (
                      <span key={h} className="rounded-full bg-gray-800 px-2.5 py-1 text-xs text-gray-300">
                        {h}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Geographic Map tab */}
        {activeTab === "geo" && (
          <div className="p-6 space-y-4">
            <h1 className="text-xl font-bold text-white">Geographic Innovation Map</h1>
            <p className="text-sm text-gray-400">US fintech open-source developer density and contribution clusters.</p>
            <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
              <div className="space-y-3">
                {[
                  { city: "San Francisco Bay Area", repos: 8432, devs: 24891, score: 100 },
                  { city: "New York City", repos: 4891, devs: 18234, score: 67 },
                  { city: "Austin, TX", repos: 1892, devs: 7102, score: 48 },
                  { city: "Boston, MA", repos: 1201, devs: 5893, score: 42 },
                  { city: "Chicago, IL", repos: 1743, devs: 6421, score: 38 },
                  { city: "Seattle, WA", repos: 1102, devs: 4891, score: 31 },
                  { city: "Miami, FL", repos: 892, devs: 3201, score: 25 },
                  { city: "Washington, DC", repos: 743, devs: 2891, score: 22 },
                ].map((c) => (
                  <div key={c.city} className="flex items-center gap-4">
                    <div className="w-36 text-sm text-gray-300 shrink-0">{c.city}</div>
                    <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                      <div
                        className="h-2 rounded-full bg-blue-500 transition-all"
                        style={{ width: `${c.score}%` }}
                      />
                    </div>
                    <div className="w-20 text-right text-xs text-gray-500">
                      {c.repos.toLocaleString()} repos
                    </div>
                    <div className="w-20 text-right text-xs text-gray-600">
                      {c.devs.toLocaleString()} devs
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* AI Chat tab */}
        {activeTab === "chat" && (
          <div className="flex h-full flex-col p-6">
            <h1 className="text-xl font-bold text-white mb-1">AI Intelligence Assistant</h1>
            <p className="text-sm text-gray-400 mb-4">
              Natural language queries over the FinTech knowledge graph, powered by Claude.
            </p>

            <div className="flex-1 rounded-xl border border-gray-800 bg-gray-900 flex flex-col overflow-hidden min-h-[500px]">
              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {chatMessages.map((m, i) => (
                  <div key={i} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                    <div
                      className={`h-8 w-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
                        m.role === "assistant" ? "bg-blue-600" : "bg-gray-700"
                      }`}
                    >
                      {m.role === "assistant" ? "AI" : "U"}
                    </div>
                    <div
                      className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap leading-relaxed ${
                        m.role === "user"
                          ? "bg-blue-600 text-white"
                          : "bg-gray-800 text-gray-100"
                      }`}
                    >
                      {m.text}
                    </div>
                  </div>
                ))}
              </div>

              {/* Example prompts */}
              {chatMessages.length <= 1 && (
                <div className="px-4 pb-2">
                  <p className="text-xs text-gray-500 mb-2">Try asking:</p>
                  <div className="flex flex-wrap gap-2">
                    {CHAT_EXAMPLES.map((q) => (
                      <button
                        key={q}
                        onClick={() => { setChatInput(q); }}
                        className="rounded-full border border-gray-700 px-3 py-1 text-xs text-gray-300 hover:border-blue-500 hover:text-blue-300 transition-colors"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Input */}
              <div className="border-t border-gray-800 p-4 flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleChat()}
                  placeholder="Ask about fintech technologies, regulations, or disruption signals…"
                  className="flex-1 rounded-xl bg-gray-800 border border-gray-700 px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                />
                <button
                  onClick={handleChat}
                  disabled={!chatInput.trim()}
                  className="h-10 px-4 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Technologies tab */}
        {activeTab === "technologies" && (
          <div className="p-6 space-y-4">
            <h1 className="text-xl font-bold text-white">Technology Taxonomy</h1>
            <p className="text-sm text-gray-400">2,847 fintech technologies tracked across all repositories.</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[
                { name: "ISO 20022", cat: "Messaging", repos: 312, maturity: "Mature", color: "green" },
                { name: "Zero-Knowledge Proofs", cat: "Cryptography", repos: 187, maturity: "Emerging", color: "purple" },
                { name: "AI AML Screening", cat: "Compliance", repos: 143, maturity: "Growing", color: "blue" },
                { name: "CBDC Infrastructure", cat: "Digital Money", repos: 67, maturity: "Emerging", color: "yellow" },
                { name: "FIX Protocol", cat: "Messaging", repos: 891, maturity: "Mature", color: "green" },
                { name: "Open Banking APIs", cat: "Infrastructure", repos: 421, maturity: "Growing", color: "blue" },
                { name: "Federated Learning", cat: "ML / AI", repos: 56, maturity: "Emerging", color: "purple" },
                { name: "Homomorphic Encryption", cat: "Cryptography", repos: 34, maturity: "Emerging", color: "red" },
                { name: "Real-Time Payments", cat: "Payments", repos: 234, maturity: "Growing", color: "blue" },
              ].map((t) => (
                <div key={t.name} className="rounded-xl border border-gray-800 bg-gray-900 p-4 space-y-2">
                  <div className="flex items-start justify-between">
                    <span className="text-sm font-semibold text-white">{t.name}</span>
                    <span className={`text-xs rounded px-1.5 py-0.5 border
                      ${t.maturity === "Mature" ? "border-green-700 bg-green-900/30 text-green-300" : ""}
                      ${t.maturity === "Growing" ? "border-blue-700 bg-blue-900/30 text-blue-300" : ""}
                      ${t.maturity === "Emerging" ? "border-yellow-700 bg-yellow-900/30 text-yellow-300" : ""}
                    `}>{t.maturity}</span>
                  </div>
                  <p className="text-xs text-gray-500">{t.cat}</p>
                  <p className="text-sm font-mono text-gray-300">{t.repos} repositories</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
