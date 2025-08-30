#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
域层 KG 合并器，实现展示用合并与去重
"""

import logging
from typing import Dict, List, Any


logger = logging.getLogger(__name__)


class KGMerger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def merge_multiple_kgs(self, kg_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            if not kg_list:
                return {"nodes": [], "edges": [], "hierarchy": "", "total_nodes": 0, "total_edges": 0, "chapters_covered": []}
            all_nodes: List[Dict[str, Any]] = []
            all_edges: List[Dict[str, Any]] = []
            all_chapters: set[str] = set()
            for kg in kg_list:
                if not isinstance(kg, dict):
                    continue
                all_nodes.extend(kg.get("nodes", []))
                all_edges.extend(kg.get("edges", []))
                all_chapters.update(kg.get("chapters_covered", []))
            merged_nodes = self._merge_nodes(all_nodes)
            merged_edges = self._merge_edges(all_edges)
            return {
                "nodes": merged_nodes,
                "edges": merged_edges,
                "hierarchy": "合并后的知识图谱",
                "total_nodes": len(merged_nodes),
                "total_edges": len(merged_edges),
                "chapters_covered": list(all_chapters),
            }
        except Exception as e:
            logger.error(f"KG 合并失败: {e}")
            return {"nodes": [], "edges": [], "hierarchy": "", "total_nodes": 0, "total_edges": 0, "chapters_covered": []}

    def _merge_nodes(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            concept_nodes: Dict[str, Dict[str, Any]] = {}
            structural_nodes: Dict[str, Dict[str, Any]] = {}
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                t = node.get("type", "")
                if t == "concept":
                    key = node.get("canonical_key", node.get("name", ""))
                    if not key:
                        continue
                    if key in concept_nodes:
                        self._merge_concept_node(concept_nodes[key], node)
                    else:
                        concept_nodes[key] = node.copy()
                else:
                    nid = node.get("id", node.get("name", ""))
                    if nid and nid not in structural_nodes:
                        structural_nodes[nid] = node.copy()
            return list(concept_nodes.values()) + list(structural_nodes.values())
        except Exception as e:
            logger.error(f"节点合并失败: {e}")
            return nodes

    def _merge_concept_node(self, existing: Dict[str, Any], new: Dict[str, Any]) -> None:
        try:
            existing_aliases = set(existing.get("aliases", [])) | set(new.get("aliases", []))
            existing["aliases"] = list(existing_aliases)
            if len(new.get("description", "")) > len(existing.get("description", "")):
                existing["description"] = new.get("description", "")
            existing["score"] = max(existing.get("score", 0.0), new.get("score", 0.0))
            if new.get("updated_at"):
                existing["updated_at"] = new["updated_at"]
        except Exception as e:
            logger.error(f"概念节点合并失败: {e}")

    def _merge_edges(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            edge_map: Dict[str, Dict[str, Any]] = {}
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                s = edge.get("source_id", "")
                t = edge.get("target_id", "")
                et = edge.get("type", "")
                if not (s and t and et):
                    continue
                evidence = edge.get("evidence", "")
                if evidence and len(evidence) > 20:
                    import hashlib
                    evi_hash = hashlib.md5(evidence.encode("utf-8")).hexdigest()[:8]
                    key = f"{s}->{t}:{et}:{evi_hash}"
                else:
                    key = f"{s}->{t}:{et}"
                if key not in edge_map:
                    edge_map[key] = edge.copy()
                else:
                    self._merge_edge_info(edge_map[key], edge)
            return list(edge_map.values())
        except Exception as e:
            logger.error(f"边合并失败: {e}")
            return edges

    def _merge_edge_info(self, existing: Dict[str, Any], new: Dict[str, Any]) -> None:
        try:
            existing["weight"] = (existing.get("weight", 1.0) + new.get("weight", 1.0)) / 2
            existing["confidence"] = max(existing.get("confidence", 0.0), new.get("confidence", 0.0))
            ev_old = existing.get("evidence", "")
            ev_new = new.get("evidence", "")
            if ev_new and ev_new not in ev_old:
                existing["evidence"] = f"{ev_old}; {ev_new}" if ev_old else ev_new
            if new.get("updated_at"):
                existing["updated_at"] = new["updated_at"]
        except Exception as e:
            logger.error(f"边信息合并失败: {e}")

__all__ = ["KGMerger"]

