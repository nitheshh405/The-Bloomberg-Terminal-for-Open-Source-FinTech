import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 503) {
      console.warn("Service unavailable — check backend connection");
    }
    return Promise.reject(error);
  }
);

// ── Types ──────────────────────────────────────────────────────────────────

export interface Repository {
  id: string;
  full_name: string;
  url: string;
  description?: string;
  language?: string;
  stars: number;
  forks: number;
  primary_sector?: string;
  fintech_domains: string[];
  innovation_score?: number;
  disruption_score?: number;
  startup_score?: number;
  compliance_risk_score?: number;
  source: string;
}

export interface PaginatedRepositories {
  items: Repository[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Technology {
  id: string;
  name: string;
  category?: string;
  description?: string;
  repo_count?: number;
}

export interface Regulation {
  id: string;
  name: string;
  full_name?: string;
  jurisdiction?: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
  size: number;
  color?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
  weight: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  node_count: number;
  edge_count: number;
}

export interface GraphStats {
  total_repos: number;
  total_devs: number;
  total_techs: number;
  high_disruption_count: number;
  startup_signal_count: number;
  avg_innovation_score: number;
}

export interface IntelligenceReport {
  filename: string;
  date: string;
  size_bytes: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  answer: string;
  cypher?: string;
  results?: unknown[];
}

// ── API client ─────────────────────────────────────────────────────────────

export const apiClient = {
  health: () =>
    api.get<{ status: string; version: string }>("/api/v1/health").then((r) => r.data),

  listRepositories: (params?: {
    page?: number;
    page_size?: number;
    sector?: string;
    min_score?: number;
    min_disruption?: number;
    language?: string;
    order_by?: string;
  }) =>
    api.get<PaginatedRepositories>("/api/v1/repositories", { params }).then((r) => r.data),

  disruptionLeaderboard: (params?: { sector?: string; limit?: number }) =>
    api.get<Repository[]>("/api/v1/repositories/leaderboard/disruption", { params }).then((r) => r.data),

  listTechnologies: (params?: { category?: string; limit?: number }) =>
    api.get<{ t: Technology; repo_count: number }[]>("/api/v1/technologies", { params }).then((r) => r.data),

  listRegulations: () =>
    api.get<{ rl: Regulation }[]>("/api/v1/regulations").then((r) => r.data),

  graphOverview: (params?: { sector?: string; min_score?: number; limit?: number }) =>
    api.get<GraphResponse>("/api/v1/graph/overview", { params }).then((r) => r.data),

  graphStats: () =>
    api.get<GraphStats>("/api/v1/graph/stats").then((r) => r.data),

  listReports: () =>
    api.get<IntelligenceReport[]>("/api/v1/intelligence/reports").then((r) => r.data),

  getReport: (date: string) =>
    api.get<{ date: string; content: string }>(`/api/v1/intelligence/reports/${date}`).then((r) => r.data),

  search: (q: string, params?: { node_type?: string; limit?: number }) =>
    api.get<unknown[]>("/api/v1/search", { params: { q, ...params } }).then((r) => r.data),

  chat: (message: string, history: ChatMessage[] = []) =>
    api.post<ChatResponse>("/api/v1/chat", { message, history }).then((r) => r.data),
};
