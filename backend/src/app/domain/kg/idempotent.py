#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KG Idempotent - 幂等ID生成与查重
工程化分层设计中的第三层：确保节点和关系的唯一性和幂等性
"""

import hashlib
import logging
import time
from typing import Dict, Any, List, Set
from datetime import datetime

from .schemas import KGNode, KGEdge, KGDict


logger = logging.getLogger(__name__)


class KGIdempotentProcessor:
    """KG幂等性处理器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_kg(self, kg_data: KGDict, context: Dict[str, Any]) -> KGDict:
        """
        对KG数据进行幂等性处理
        
        Args:
            kg_data: 标准化后的KG数据
            context: 上下文信息
            
        Returns:
            KGDict: 处理后的KG数据，包含幂等ID
        """
        try:
            current_time = datetime.utcnow()
            
            # 处理节点
            processed_nodes = []
            node_id_map = {}  # 原始ID -> 幂等ID映射
            
            for node in kg_data.nodes:
                # 生成幂等节点ID
                canonical_name = self._canonicalize_name(node.name)
                node_id = self._generate_node_id(canonical_name, node.type, context.get("scope", ""))
                
                # 创建新的节点对象
                processed_node = KGNode(
                    id=node_id,
                    name=canonical_name,
                    type=node.type,
                    desc=node.desc,
                    aliases=self._deduplicate_aliases(node.aliases, canonical_name),
                    scope=context.get("scope", node.scope),
                    created_at=current_time,
                    updated_at=current_time
                )
                
                processed_nodes.append(processed_node)
                node_id_map[node.id] = node_id
            
            # 处理边
            processed_edges = []
            edge_fingerprints = set()  # 用于去重
            
            for edge in kg_data.edges:
                # 映射源和目标节点ID
                source_id = node_id_map.get(edge.source, edge.source)
                target_id = node_id_map.get(edge.target, edge.target)
                
                # 跳过无效的边（节点不存在）
                if source_id not in node_id_map.values() or target_id not in node_id_map.values():
                    self.logger.warning(f"跳过无效边: {edge.source} -> {edge.target}")
                    continue
                
                # 生成关系ID
                rid = self._generate_relation_id(
                    source_id, 
                    target_id, 
                    edge.type, 
                    context.get("scope", ""),
                    edge.desc
                )
                
                # 创建边的指纹用于去重
                edge_fingerprint = f"{source_id}|{target_id}|{edge.type}|{context.get('scope', '')}"
                
                if edge_fingerprint in edge_fingerprints:
                    self.logger.debug(f"跳过重复边: {edge_fingerprint}")
                    continue
                
                edge_fingerprints.add(edge_fingerprint)
                
                # 创建新的边对象
                processed_edge = KGEdge(
                    rid=rid,
                    type=edge.type,
                    source=source_id,
                    target=target_id,
                    desc=edge.desc,
                    confidence=edge.confidence,
                    weight=edge.weight,
                    scope=context.get("scope", edge.scope),
                    src_section=context.get("section_id", ""),
                    created_at=current_time
                )
                
                processed_edges.append(processed_edge)
            
            # 返回处理后的KG数据
            return KGDict(
                nodes=processed_nodes,
                edges=processed_edges,
                hierarchy=kg_data.hierarchy,
                total_nodes=len(processed_nodes),
                total_edges=len(processed_edges),
                chapters_covered=kg_data.chapters_covered
            )
            
        except Exception as e:
            self.logger.error(f"KG幂等性处理失败: {e}")
            return kg_data  # 返回原始数据
    
    def _canonicalize_name(self, name: str) -> str:
        """标准化名称"""
        if not name:
            return ""
        
        # 基本清理
        canonical = name.strip()
        
        # 移除多余空格
        canonical = ' '.join(canonical.split())
        
        # TODO: 可以添加更多标准化规则
        # - 同义词替换
        # - 词形还原
        # - 大小写标准化
        
        return canonical
    
    def _generate_node_id(self, canonical_name: str, node_type: str, scope: str) -> str:
        """
        生成节点的幂等ID
        
        使用 slug(canonical_name) + type + scope 的组合
        """
        if not canonical_name:
            # 生成随机ID作为后备
            return f"node_{int(time.time() * 1000)}"
        
        # 创建slug
        slug = self._create_slug(canonical_name)
        
        # 组合ID组件
        id_components = [slug]
        if node_type and node_type != "Concept":
            id_components.append(node_type.lower())
        if scope:
            id_components.append(self._create_slug(scope)[:8])  # 限制scope长度
        
        node_id = "_".join(id_components)
        
        # 确保ID不会太长
        if len(node_id) > 64:
            # 使用哈希缩短
            hash_suffix = hashlib.md5(node_id.encode()).hexdigest()[:8]
            node_id = node_id[:50] + "_" + hash_suffix
        
        return node_id
    
    def _generate_relation_id(self, source: str, target: str, rel_type: str, scope: str, desc: str = "") -> str:
        """
        生成关系的幂等ID
        
        使用 sha256(source|target|type|scope|content_hash)[:16]
        """
        # 创建内容哈希
        content_parts = [source, target, rel_type, scope]
        if desc:
            content_parts.append(desc)
        
        content = "|".join(content_parts)
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        return content_hash[:16]
    
    def _create_slug(self, text: str) -> str:
        """创建URL友好的slug"""
        import re
        
        if not text:
            return ""
        
        # 转换为小写
        slug = text.lower()
        
        # 替换空格和特殊字符为下划线
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_-]+', '_', slug)
        
        # 移除首尾下划线
        slug = slug.strip('_')
        
        return slug
    
    def _deduplicate_aliases(self, aliases: List[str], canonical_name: str) -> List[str]:
        """去重别名列表"""
        if not aliases:
            return []
        
        # 创建集合去重，并排除canonical_name
        unique_aliases = set()
        for alias in aliases:
            if alias and alias.strip() and alias.strip() != canonical_name:
                unique_aliases.add(alias.strip())
        
        return sorted(list(unique_aliases))


def generate_content_hash(content: str) -> str:
    """生成内容哈希（保持与现有系统兼容）"""
    if not content:
        return ""
    return hashlib.md5(content.encode()).hexdigest()


def generate_book_id(topic: str, language: str = "zh") -> str:
    """生成整书ID"""
    if not topic:
        return f"book_{int(time.time() * 1000)}"
    
    # 创建基于主题的book_id
    slug = KGIdempotentProcessor()._create_slug(topic)
    if language and language != "zh":
        slug += f"_{language}"
    
    return f"book_{slug}"