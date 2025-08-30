#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Protocol, Dict, Any, List


class KGStore(Protocol):
    def merge_node(self, node: Dict[str, Any]) -> bool: ...
    def merge_edge(self, edge: Dict[str, Any]) -> bool: ...
    def delete_edges_by_src(self, section_id: str) -> int: ...
    def get_stats(self) -> Dict[str, int]: ...
    
    # B1方案新增：可选的scope相关方法
    def delete_edges_by_scope(self, scope: str) -> int: 
        """按scope删除关系，可选实现"""
        return 0


class MemoryKGStore:
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, Dict[str, Any]] = {}

    def merge_node(self, node: Dict[str, Any]) -> bool:
        nid = node.get("id")
        if not nid:
            return False
        existing = self.nodes.get(nid)
        if existing:
            existing_aliases = set(existing.get("aliases", [])) | set(node.get("aliases", []))
            existing["aliases"] = list(existing_aliases)
            if len(node.get("description", "")) > len(existing.get("description", "")):
                existing["description"] = node.get("description", "")
            existing["score"] = max(existing.get("score", 0), node.get("score", 0))
            existing["updated_at"] = node.get("updated_at", existing.get("updated_at"))
        else:
            self.nodes[nid] = node.copy()
        return True

    def merge_edge(self, edge: Dict[str, Any]) -> bool:
        eid = edge.get("id")
        if not eid:
            return False
        self.edges[eid] = edge.copy()
        return True

    def delete_edges_by_src(self, section_id: str) -> int:
        to_delete = [eid for eid, e in self.edges.items() if e.get("src") == section_id]
        for eid in to_delete:
            del self.edges[eid]
        return len(to_delete)

    def delete_edges_by_scope(self, scope: str) -> int:
        """按scope删除关系"""
        to_delete = [eid for eid, e in self.edges.items() if e.get("scope") == scope]
        for eid in to_delete:
            del self.edges[eid]
        return len(to_delete)

    def get_stats(self) -> Dict[str, int]:
        return {"total_nodes": len(self.nodes), "total_edges": len(self.edges)}

