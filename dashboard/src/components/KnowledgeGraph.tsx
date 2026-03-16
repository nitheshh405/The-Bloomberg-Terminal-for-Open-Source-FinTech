/**
 * Interactive Knowledge Graph Component
 * D3.js force-directed graph for exploring the FinTech ecosystem.
 * Renders Repository, Technology, FinancialSector, and Regulation nodes.
 */

import React, { useEffect, useRef, useCallback } from "react";
import * as d3 from "d3";
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";

interface GraphNode {
  id: string;
  label: string;
  type: string;
  size: number;
  color: string;
  properties: Record<string, unknown>;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface GraphEdge {
  source: string | GraphNode;
  target: string | GraphNode;
  label: string;
  weight: number;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface KnowledgeGraphProps {
  sector?: string;
  minScore?: number;
  onNodeClick?: (node: GraphNode) => void;
}

const TYPE_COLORS: Record<string, string> = {
  Repository: "#4f8ef7",
  Technology: "#f74f4f",
  FinancialSector: "#9b4ff7",
  Regulation: "#f7e64f",
  Developer: "#f7a24f",
  Organization: "#4ff78e",
};

export const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({
  sector,
  minScore = 50,
  onNodeClick,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: graphData, isLoading } = useQuery<GraphData>({
    queryKey: ["graph-overview", sector, minScore],
    queryFn: () =>
      api
        .get("/api/v1/graph/overview", { params: { sector, min_score: minScore, limit: 150 } })
        .then((r) => r.data),
  });

  const renderGraph = useCallback(
    (data: GraphData) => {
      if (!svgRef.current || !containerRef.current) return;

      const container = containerRef.current;
      const width = container.clientWidth;
      const height = container.clientHeight || 600;

      // Clear previous render
      d3.select(svgRef.current).selectAll("*").remove();

      const svg = d3
        .select(svgRef.current)
        .attr("width", width)
        .attr("height", height);

      // Zoom support
      const g = svg.append("g");
      const zoom = d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.1, 4])
        .on("zoom", (event) => g.attr("transform", event.transform));
      svg.call(zoom);

      // Arrow markers
      svg
        .append("defs")
        .append("marker")
        .attr("id", "arrow")
        .attr("viewBox", "0 -5 10 10")
        .attr("refX", 20)
        .attr("refY", 0)
        .attr("markerWidth", 6)
        .attr("markerHeight", 6)
        .attr("orient", "auto")
        .append("path")
        .attr("d", "M0,-5L10,0L0,5")
        .attr("fill", "#4b5563");

      // Force simulation
      const simulation = d3
        .forceSimulation<GraphNode>(data.nodes)
        .force(
          "link",
          d3
            .forceLink<GraphNode, GraphEdge>(data.edges)
            .id((d) => d.id)
            .distance(80)
            .strength(0.3)
        )
        .force("charge", d3.forceManyBody().strength(-200))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide<GraphNode>().radius((d) => d.size * 6 + 10));

      // Edges
      const link = g
        .append("g")
        .selectAll("line")
        .data(data.edges)
        .join("line")
        .attr("stroke", "#374151")
        .attr("stroke-opacity", 0.6)
        .attr("stroke-width", (d) => Math.sqrt(d.weight || 1))
        .attr("marker-end", "url(#arrow)");

      // Edge labels (only show for important relationships)
      const linkLabel = g
        .append("g")
        .selectAll("text")
        .data(data.edges.filter((_, i) => i < 50))
        .join("text")
        .attr("font-size", 8)
        .attr("fill", "#6b7280")
        .attr("text-anchor", "middle")
        .text((d) => d.label);

      // Nodes
      const node = g
        .append("g")
        .selectAll("g")
        .data(data.nodes)
        .join("g")
        .attr("cursor", "pointer")
        .call(
          d3
            .drag<SVGGElement, GraphNode>()
            .on("start", (event, d) => {
              if (!event.active) simulation.alphaTarget(0.3).restart();
              d.fx = d.x;
              d.fy = d.y;
            })
            .on("drag", (event, d) => {
              d.fx = event.x;
              d.fy = event.y;
            })
            .on("end", (event, d) => {
              if (!event.active) simulation.alphaTarget(0);
              d.fx = null;
              d.fy = null;
            })
        )
        .on("click", (event, d) => {
          event.stopPropagation();
          onNodeClick?.(d);
        });

      // Node circles
      node
        .append("circle")
        .attr("r", (d) => d.size * 4 + 5)
        .attr("fill", (d) => d.color || TYPE_COLORS[d.type] || "#6b7280")
        .attr("fill-opacity", 0.85)
        .attr("stroke", "#1f2937")
        .attr("stroke-width", 1.5);

      // Node labels
      node
        .append("text")
        .attr("x", 0)
        .attr("y", (d) => d.size * 4 + 14)
        .attr("text-anchor", "middle")
        .attr("font-size", 9)
        .attr("fill", "#d1d5db")
        .text((d) => d.label.length > 18 ? d.label.slice(0, 16) + "…" : d.label);

      // Tooltip
      const tooltip = d3
        .select(container)
        .append("div")
        .attr("class", "graph-tooltip")
        .style("position", "absolute")
        .style("background", "#1f2937")
        .style("border", "1px solid #374151")
        .style("border-radius", "6px")
        .style("padding", "8px 12px")
        .style("font-size", "12px")
        .style("color", "#f9fafb")
        .style("pointer-events", "none")
        .style("opacity", 0)
        .style("max-width", "220px");

      node
        .on("mouseenter", (event, d) => {
          const props = d.properties as any;
          tooltip
            .html(
              `<strong>${d.label}</strong><br/>
               <span style="color:#9ca3af">Type: ${d.type}</span><br/>
               ${props.stars ? `⭐ ${props.stars.toLocaleString()}<br/>` : ""}
               ${props.score ? `Innovation: ${props.score.toFixed(1)}<br/>` : ""}
               ${props.disruption ? `Disruption: ${props.disruption.toFixed(1)}` : ""}`
            )
            .style("opacity", 1)
            .style("left", `${event.offsetX + 12}px`)
            .style("top", `${event.offsetY - 28}px`);
        })
        .on("mouseleave", () => tooltip.style("opacity", 0));

      // Simulation tick
      simulation.on("tick", () => {
        link
          .attr("x1", (d) => (d.source as GraphNode).x!)
          .attr("y1", (d) => (d.source as GraphNode).y!)
          .attr("x2", (d) => (d.target as GraphNode).x!)
          .attr("y2", (d) => (d.target as GraphNode).y!);

        linkLabel
          .attr("x", (d) => (((d.source as GraphNode).x! + (d.target as GraphNode).x!) / 2))
          .attr("y", (d) => (((d.source as GraphNode).y! + (d.target as GraphNode).y!) / 2));

        node.attr("transform", (d) => `translate(${d.x},${d.y})`);
      });
    },
    [onNodeClick]
  );

  useEffect(() => {
    if (graphData) {
      renderGraph(graphData);
    }
  }, [graphData, renderGraph]);

  // Legend
  const legend = Object.entries(TYPE_COLORS).slice(0, 5);

  return (
    <div ref={containerRef} className="relative w-full h-full min-h-[600px]">
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-950/60 z-10">
          <div className="text-gray-400 text-sm">Loading knowledge graph…</div>
        </div>
      )}

      <svg ref={svgRef} className="w-full h-full bg-gray-950 rounded-lg" />

      {/* Legend */}
      <div className="absolute bottom-4 left-4 flex flex-col gap-1.5 bg-gray-900/90 border border-gray-800 rounded-lg p-3">
        {legend.map(([type, color]) => (
          <div key={type} className="flex items-center gap-2 text-xs text-gray-300">
            <span
              className="inline-block h-3 w-3 rounded-full"
              style={{ backgroundColor: color }}
            />
            {type}
          </div>
        ))}
      </div>
    </div>
  );
};
