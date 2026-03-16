/**
 * Main Dashboard Page
 * Overview of FinTech Intelligence Terminal intelligence with key metrics,
 * top repositories, and sector distribution.
 */

import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  TrendingUp,
  Database,
  Users,
  AlertTriangle,
  Zap,
  Shield,
  BarChart2,
  Globe,
} from "lucide-react";
import { api } from "../services/api";
import { MetricCard } from "../components/MetricCard";
import { RepositoryTable } from "../components/RepositoryTable";
import { SectorDistributionChart } from "../components/SectorDistributionChart";
import { InnovationRadar } from "../components/InnovationRadar";
import { DisruptionLeaderboard } from "../components/DisruptionLeaderboard";

export default function Dashboard() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["graph-stats"],
    queryFn: () => api.get("/api/v1/graph/stats").then((r) => r.data),
    refetchInterval: 300_000, // refresh every 5 min
  });

  const { data: topRepos, isLoading: reposLoading } = useQuery({
    queryKey: ["top-repositories"],
    queryFn: () =>
      api
        .get("/api/v1/repositories", {
          params: { order_by: "innovation_score", page_size: 10, min_score: 50 },
        })
        .then((r) => r.data.items),
  });

  const { data: sectorData } = useQuery({
    queryKey: ["sector-distribution"],
    queryFn: () =>
      api
        .get("/api/v1/graph/stats")
        .then((r) => r.data),
  });

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart2 className="h-7 w-7 text-blue-400" />
            <div>
              <h1 className="text-xl font-bold text-white">
                FinTech Intelligence Terminal
              </h1>
              <p className="text-xs text-gray-400">
                Bloomberg Terminal for Open-Source FinTech Innovation
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 rounded-full bg-green-900/40 px-3 py-1 text-xs text-green-400">
              <span className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
              Live
            </span>
          </div>
        </div>
      </header>

      <main className="px-6 py-8 space-y-8">
        {/* ── KPI Cards ────────────────────────────────────────────────── */}
        <section>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-500">
            Platform Overview
          </h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard
              icon={<Database className="h-5 w-5 text-blue-400" />}
              label="Total Repositories"
              value={stats?.total_repos?.toLocaleString() ?? "—"}
              loading={statsLoading}
              color="blue"
            />
            <MetricCard
              icon={<Users className="h-5 w-5 text-orange-400" />}
              label="Developers Tracked"
              value={stats?.total_devs?.toLocaleString() ?? "—"}
              loading={statsLoading}
              color="orange"
            />
            <MetricCard
              icon={<Zap className="h-5 w-5 text-purple-400" />}
              label="Technologies"
              value={stats?.total_techs?.toLocaleString() ?? "—"}
              loading={statsLoading}
              color="purple"
            />
            <MetricCard
              icon={<AlertTriangle className="h-5 w-5 text-red-400" />}
              label="High Disruption"
              value={stats?.high_disruption_count?.toLocaleString() ?? "—"}
              loading={statsLoading}
              color="red"
              subtitle="Score ≥ 70"
            />
            <MetricCard
              icon={<TrendingUp className="h-5 w-5 text-green-400" />}
              label="Startup Signals"
              value={stats?.startup_signal_count?.toLocaleString() ?? "—"}
              loading={statsLoading}
              color="green"
              subtitle="Score ≥ 65"
            />
            <MetricCard
              icon={<Shield className="h-5 w-5 text-yellow-400" />}
              label="Avg Innovation"
              value={
                stats?.avg_innovation_score
                  ? `${stats.avg_innovation_score.toFixed(1)}`
                  : "—"
              }
              loading={statsLoading}
              color="yellow"
              subtitle="out of 100"
            />
          </div>
        </section>

        {/* ── Main Content Grid ─────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Top Repositories Table — spans 2 columns */}
          <div className="lg:col-span-2">
            <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
              <h2 className="mb-4 flex items-center gap-2 text-base font-semibold text-white">
                <TrendingUp className="h-4 w-4 text-blue-400" />
                Top Innovation Repositories
              </h2>
              <RepositoryTable repos={topRepos ?? []} loading={reposLoading} />
            </div>
          </div>

          {/* Disruption Leaderboard — 1 column */}
          <div>
            <DisruptionLeaderboard />
          </div>
        </div>

        {/* ── Charts Row ────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            <h2 className="mb-4 text-base font-semibold text-white">
              Sector Distribution
            </h2>
            <SectorDistributionChart />
          </div>

          <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
            <h2 className="mb-4 text-base font-semibold text-white">
              Innovation Radar
            </h2>
            <InnovationRadar />
          </div>
        </div>
      </main>
    </div>
  );
}
