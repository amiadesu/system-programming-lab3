import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import type { AstNode } from "../../types/ast";
import "./AstTree.css";

interface AstTreeProps {
  root: AstNode | null;
}

interface TreeDatum {
  id: string;
  node: AstNode;
  children: TreeDatum[];
}

const NODE_HORIZONTAL_SPACING = 118;
const NODE_VERTICAL_SPACING = 68;
const PADDING = 40;
const MIN_SCALE = 0.1;
const MAX_SCALE = 4;

function buildTree(node: AstNode, id: string): TreeDatum {
  return {
    id,
    node,
    children: node.children.map((child, index) => buildTree(child, `${id}.${index}`)),
  };
}

export default function AstTree({ root }: AstTreeProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const canvasRef = useRef<SVGGElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const treeData = useMemo(() => (root ? buildTree(root, "0") : null), [root]);

  useEffect(() => setCollapsed(new Set()), [treeData]);

  const fitToView = useCallback(() => {
    const svgElement = svgRef.current;
    const canvasElement = canvasRef.current;
    const zoom = zoomRef.current;
    if (!svgElement || !canvasElement || !zoom) return;

    const bounds = canvasElement.getBBox();
    if (bounds.width === 0 || bounds.height === 0) return;

    const { width, height } = svgElement.getBoundingClientRect();
    if (width === 0 || height === 0) return;

    const scale = Math.min(
      MAX_SCALE,
      (width - PADDING) / bounds.width,
      (height - PADDING) / bounds.height,
    );
    const translateX = width / 2 - scale * (bounds.x + bounds.width / 2);
    const translateY = PADDING / 2 - scale * bounds.y;

    d3.select(svgElement)
      .transition()
      .duration(250)
      .call(zoom.transform, d3.zoomIdentity.translate(translateX, translateY).scale(scale));
  }, []);

  const toggleNode = useCallback((id: string, hasChildren: boolean) => {
    if (!hasChildren) return;
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    const svgElement = svgRef.current;
    const canvasElement = canvasRef.current;
    if (!svgElement || !canvasElement || !treeData) return;

    const svg = d3.select(svgElement);
    const canvas = d3.select(canvasElement);
    canvas.selectAll("*").remove();

    if (!zoomRef.current) {
      const zoom = d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([MIN_SCALE, MAX_SCALE])
        .extent(function () {
          const { width, height } = this.getBoundingClientRect();
          return [
            [0, 0],
            [width, height],
          ];
        })
        .on("zoom", (event) => canvas.attr("transform", event.transform.toString()));
      svg.call(zoom);
      svg.on("dblclick.zoom", null);
      zoomRef.current = zoom;
    }

    const hierarchyRoot = d3.hierarchy(treeData, (datum) =>
      collapsed.has(datum.id) ? undefined : datum.children,
    );
    const layoutRoot = d3
      .tree<TreeDatum>()
      .nodeSize([NODE_HORIZONTAL_SPACING, NODE_VERTICAL_SPACING])(hierarchyRoot);

    canvas
      .selectAll("path.ast-link")
      .data(layoutRoot.links())
      .join("path")
      .attr("class", "ast-link")
      .attr(
        "d",
        d3
          .linkVertical<d3.HierarchyPointLink<TreeDatum>, d3.HierarchyPointNode<TreeDatum>>()
          .x((node) => node.x)
          .y((node) => node.y),
      );

    const nodeGroups = canvas
      .selectAll("g.ast-node")
      .data(layoutRoot.descendants())
      .join("g")
      .attr("class", (node) =>
        collapsed.has(node.data.id) ? "ast-node ast-node--collapsed" : "ast-node",
      )
      .attr("transform", (node) => `translate(${node.x}, ${node.y})`)
      .on("click", (event, node) => {
        event.stopPropagation();
        toggleNode(node.data.id, node.data.children.length > 0);
      });

    nodeGroups
      .append("circle")
      .attr("class", "ast-node-hit")
      .attr("r", 22)
      .attr("cy", 2);

    nodeGroups.append("circle").attr("class", "ast-node-dot").attr("r", 5);

    nodeGroups
      .filter((node) => node.data.node.role !== null)
      .append("text")
      .attr("class", "ast-node-role")
      .attr("dy", -22)
      .attr("text-anchor", "middle")
      .text((node) => node.data.node.role as string);

    nodeGroups
      .append("text")
      .attr("class", "ast-node-type")
      .attr("dy", -10)
      .attr("text-anchor", "middle")
      .text((node) => node.data.node.type);

    nodeGroups
      .filter((node) => node.data.node.label !== null)
      .append("text")
      .attr("class", "ast-node-label")
      .attr("dy", 18)
      .attr("text-anchor", "middle")
      .text((node) => node.data.node.label as string);

    nodeGroups
      .filter((node) => collapsed.has(node.data.id))
      .append("text")
      .attr("class", "ast-node-count")
      .attr("dy", 4)
      .attr("dx", 12)
      .text((node) => `+${countDescendants(node.data)}`);
  }, [treeData, collapsed, toggleNode]);

  useEffect(() => {
    if (treeData) fitToView();
  }, [treeData, fitToView]);

  if (!root) {
    return <div className="ast-tree ast-tree--empty">AST з'явиться тут після компіляції</div>;
  }

  return (
    <div className="ast-tree">
      <div className="ast-tree-toolbar">
        <span className="ast-tree-hint">Колесо — масштаб, перетягування — переміщення, клік по вузлу — згорнути</span>
        <button className="ast-tree-button" onClick={fitToView}>
          Вмістити
        </button>
      </div>
      <svg ref={svgRef} className="ast-tree-canvas">
        <g ref={canvasRef} />
      </svg>
    </div>
  );
}

function countDescendants(datum: TreeDatum): number {
  return datum.children.reduce((total, child) => total + 1 + countDescendants(child), 0);
}