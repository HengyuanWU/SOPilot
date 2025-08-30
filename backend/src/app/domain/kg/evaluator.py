#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any, List


logger = logging.getLogger(__name__)


class KGEvaluator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_graph_structure(self, kg: Dict[str, Any]) -> Dict[str, Any]:
        try:
            nodes = kg.get("nodes", [])
            edges = kg.get("edges", [])
            if not nodes:
                return {"connectivity_score": 0.0, "components": 0, "max_component_size": 0}
            graph = {node.get("id", node.get("name", "")): [] for node in nodes}
            for edge in edges:
                s = edge.get("source_id", edge.get("source", ""))
                t = edge.get("target_id", edge.get("target", ""))
                if s in graph and t in graph:
                    graph[s].append(t)
                    graph[t].append(s)
            visited = set()
            components: List[List[str]] = []
            def dfs(n: str, comp: List[str]):
                if n in visited:
                    return
                visited.add(n)
                comp.append(n)
                for nb in graph.get(n, []):
                    dfs(nb, comp)
            for nid in graph:
                if nid not in visited:
                    c: List[str] = []
                    dfs(nid, c)
                    components.append(c)
            max_component_size = max((len(c) for c in components), default=0)
            connectivity_score = max_component_size / len(nodes) if nodes else 0.0
            return {
                "connectivity_score": connectivity_score,
                "components": len(components),
                "max_component_size": max_component_size,
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            }
        except Exception:
            logger.error("分析图结构失败", exc_info=True)
            return {"connectivity_score": 0.0, "components": 0, "max_component_size": 0}

    def extract_node_relationships(self, kg: Dict[str, Any]) -> Dict[str, Any]:
        try:
            edges = kg.get("edges", [])
            relationship_types: Dict[str, int] = {}
            for edge in edges:
                et = edge.get("type", "UNKNOWN")
                relationship_types[et] = relationship_types.get(et, 0) + 1
            nodes_count = len(kg.get("nodes", []))
            edges_count = len(edges)
            relation_richness = min(1.0, edges_count / nodes_count) if nodes_count > 0 else 0.0
            return {
                "relationship_types": relationship_types,
                "relation_richness": relation_richness,
                "total_relationships": edges_count,
            }
        except Exception:
            logger.error("提取节点关系失败", exc_info=True)
            return {"relationship_types": {}, "relation_richness": 0.0, "total_relationships": 0}

    def assess_knowledge_coverage(self, kg: Dict[str, Any], chapters: List[Dict[str, Any]] = None, global_keywords: List[str] = None) -> Dict[str, Any]:
        try:
            nodes = kg.get("nodes", [])
            all_subchapters = set()
            if chapters:
                for chapter in chapters:
                    subs = chapter.get("subchapters", [])
                    if subs:
                        for s in subs:
                            all_subchapters.add(s["title"])
                    else:
                        all_subchapters.add(chapter["title"])
            all_keywords = set(global_keywords or [])
            covered_subchapters = {n.get("subchapter", "") for n in nodes if n.get("subchapter") and n.get("subchapter") != "未知子章节"}
            subchapter_coverage = (len(covered_subchapters) / len(all_subchapters)) if all_subchapters else 1.0
            covered_keywords = set()
            for n in nodes:
                nm = (n.get("name", "") or "").lower()
                desc = (n.get("description", "") or "").lower()
                aliases = n.get("aliases", [])
                for kw in list(all_keywords):
                    kl = kw.lower()
                    if kl in nm or kl in desc or any(kl in (a or "").lower() for a in aliases):
                        covered_keywords.add(kw)
            keyword_coverage = (len(covered_keywords) / len(all_keywords)) if all_keywords else 1.0
            structure = self.analyze_graph_structure(kg)
            relations = self.extract_node_relationships(kg)
            coverage_score = 0.4 * subchapter_coverage + 0.3 * keyword_coverage + 0.2 * structure.get("connectivity_score", 0.0) + 0.1 * relations.get("relation_richness", 0.0)
            return {
                "coverage_score": coverage_score,
                "subchapter_coverage": subchapter_coverage,
                "keyword_coverage": keyword_coverage,
                "connectivity_score": structure.get("connectivity_score", 0.0),
                "relation_richness": relations.get("relation_richness", 0.0),
                "covered_subchapters": list(covered_subchapters),
                "covered_keywords": list(covered_keywords),
                "total_subchapters": len(all_subchapters),
                "total_keywords": len(all_keywords),
            }
        except Exception:
            logger.error("评估知识覆盖度失败", exc_info=True)
            return {"coverage_score": 0.0, "subchapter_coverage": 0.0, "keyword_coverage": 0.0, "connectivity_score": 0.0, "relation_richness": 0.0}

