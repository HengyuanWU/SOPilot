#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from typing import Dict, List, Any


logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "theta_add": 0.55,
    "theta_show": 0.60,
    "min_evidence_count": 2,
}


class KGThresholds:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.thresholds = DEFAULT_THRESHOLDS.copy()
        kg_config = self.config.get("kg", {})
        self.thresholds.update(kg_config.get("thresholds", {}))

    def get_threshold(self, name: str) -> float:
        return self.thresholds.get(name, DEFAULT_THRESHOLDS.get(name, 0.0))

    def filter_edges_for_storage(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        theta_add = self.get_threshold("theta_add")
        return [e for e in edges if e.get("confidence", 0.0) >= theta_add]

    def filter_edges_for_display(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        theta_show = self.get_threshold("theta_show")
        min_evidence_count = self.get_threshold("min_evidence_count")
        filtered: List[Dict[str, Any]] = []
        for e in edges:
            conf = e.get("confidence", 0.0)
            ev = e.get("evidence", "")
            cnt = len(ev.split(";")) if ev else 1
            if conf >= theta_show and cnt >= min_evidence_count:
                filtered.append(e)
        return filtered
    
    def apply_thresholds(self, kg_data: Dict[str, Any]) -> Dict[str, Any]:
        """应用阈值过滤到知识图谱数据"""
        try:
            # 过滤节点（暂时保留所有节点）
            filtered_nodes = kg_data.get("nodes", [])
            
            # 过滤边
            edges = kg_data.get("edges", [])
            filtered_edges = self.filter_edges_for_storage(edges)
            
            # 创建过滤后的KG数据
            filtered_kg = kg_data.copy()
            filtered_kg["nodes"] = filtered_nodes
            filtered_kg["edges"] = filtered_edges
            
            logger.info(f"阈值过滤: 节点 {len(filtered_nodes)}, 边 {len(filtered_edges)}/{len(edges)}")
            
            return filtered_kg
            
        except Exception as e:
            logger.error(f"应用阈值失败: {e}")
            return kg_data

