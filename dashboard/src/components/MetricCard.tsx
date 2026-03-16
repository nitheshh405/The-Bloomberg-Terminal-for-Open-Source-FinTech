import React from "react";

interface MetricCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  subtitle?: string;
  loading?: boolean;
  color?: "blue" | "orange" | "purple" | "red" | "green" | "yellow";
}

const COLOR_MAP = {
  blue: "border-blue-800 bg-blue-900/20",
  orange: "border-orange-800 bg-orange-900/20",
  purple: "border-purple-800 bg-purple-900/20",
  red: "border-red-800 bg-red-900/20",
  green: "border-green-800 bg-green-900/20",
  yellow: "border-yellow-800 bg-yellow-900/20",
};

export const MetricCard: React.FC<MetricCardProps> = ({
  icon,
  label,
  value,
  subtitle,
  loading = false,
  color = "blue",
}) => (
  <div
    className={`rounded-xl border p-4 ${COLOR_MAP[color]} flex flex-col gap-2`}
  >
    <div className="flex items-center gap-2">
      {icon}
      <span className="text-xs font-medium text-gray-400">{label}</span>
    </div>
    {loading ? (
      <div className="h-7 w-20 animate-pulse rounded bg-gray-700" />
    ) : (
      <span className="text-2xl font-bold text-white">{value}</span>
    )}
    {subtitle && (
      <span className="text-xs text-gray-500">{subtitle}</span>
    )}
  </div>
);
