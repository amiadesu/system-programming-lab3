import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { AstNode } from "../../types/ast";
import "./AstTree.css";

interface AstTreeProps {
  root: AstNode | null;
}

const NODE_HORIZONTAL_SPACING = 118;
const NODE_VERTICAL_SPACING = 68;
const MARGIN = { top: 32, right: 24, bottom: 24, left: 24 };

export default function AstTree({ root }: AstTreeProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const svgElement = svgRef.current;
    if (!svgElement) return;

    const svg = d3.select(svgElement);
    svg.selectAll("*").remove();
    if (!root) return;

    const hierarchyRoot = d3.hierarchy(root, (node) => node.children);
    const treeLayout = d3
      .tree<AstNode>()
      .nodeSize([NODE_HORIZONTAL_SPACING, NODE_VERTICAL_SPACING]);
    const layoutRoot = treeLayout(hierarchyRoot);

    const nodes = layoutRoot.descendants();
    const minX = d3.min(nodes, (node) => node.x) ?? 0;
    const maxX = d3.max(nodes, (node) => node.x) ?? 0;
    const maxY = d3.max(nodes, (node) => node.y) ?? 0;

    const width = maxX - minX + MARGIN.left + MARGIN.right;
    const height = maxY + MARGIN.top + MARGIN.bottom + NODE_VERTICAL_SPACING;

    svg.attr("viewBox", `0 0 ${width} ${height}`).attr("width", "100%").attr("height", height);

    const canvas = svg
      .append("g")
      .attr("transform", `translate(${MARGIN.left - minX}, ${MARGIN.top})`);

    canvas
      .selectAll("path.ast-link")
      .data(layoutRoot.links())
      .join("path")
      .attr("class", "ast-link")
      .attr(
        "d",
        d3
          .linkVertical<d3.HierarchyPointLink<AstNode>, d3.HierarchyPointNode<AstNode>>()
          .x((node) => node.x)
          .y((node) => node.y),
      );

    const nodeGroups = canvas
      .selectAll("g.ast-node")
      .data(nodes)
      .join("g")
      .attr("class", "ast-node")
      .attr("transform", (node) => `translate(${node.x}, ${node.y})`);

    nodeGroups.append("circle").attr("r", 5);

    nodeGroups
      .filter((node) => node.data.role !== null)
      .append("text")
      .attr("class", "ast-node-role")
      .attr("dy", -22)
      .attr("text-anchor", "middle")
      .text((node) => node.data.role as string);

    nodeGroups
      .append("text")
      .attr("class", "ast-node-type")
      .attr("dy", -10)
      .attr("text-anchor", "middle")
      .text((node) => node.data.type);

    nodeGroups
      .filter((node) => node.data.label !== null)
      .append("text")
      .attr("class", "ast-node-label")
      .attr("dy", 18)
      .attr("text-anchor", "middle")
      .text((node) => node.data.label as string);
  }, [root]);

  if (!root) {
    return <div className="ast-tree ast-tree--empty">AST з'явиться тут після компіляції</div>;
  }

  return (
    <div className="ast-tree">
      <svg ref={svgRef} />
    </div>
  );
}