#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体提取器

从文档块中提取实体，并与知识图谱中的实体进行匹配
"""

import logging
import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """提取的实体"""
    text: str
    start_pos: int
    end_pos: int
    entity_type: str
    confidence: float
    kg_entity_id: Optional[str] = None  # 匹配的KG实体ID


class EntityExtractor:
    """实体提取器 - 基于简单规则和KG匹配"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 简单的实体模式 (可以扩展为更复杂的NLP)
        self.patterns = {
            "CONCEPT": [
                r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',  # 大写开头的概念
                r'\b(?:算法|模型|方法|技术|框架|库|工具)\b',
                r'\b(?:数据结构|设计模式|编程语言)\b'
            ],
            "TECHNICAL_TERM": [
                r'\b[A-Z]{2,}\b',  # 全大写缩写
                r'\b\w+(?:API|SDK|IDE|ORM|MVC|MVP|MVVM)\b',
                r'\b(?:HTTP|HTTPS|TCP|UDP|JSON|XML|HTML|CSS|SQL)\b'
            ],
            "CODE_ELEMENT": [
                r'\b[a-z_][a-z0-9_]*\(\)',  # 函数调用
                r'\b[A-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)*\b',  # 类名
                r'`[^`]+`'  # 代码片段
            ]
        }
    
    def extract_entities(self, text: str, kg_entities: List[Dict[str, Any]] = None) -> List[ExtractedEntity]:
        """
        从文本中提取实体
        
        Args:
            text: 输入文本
            kg_entities: 知识图谱中的实体列表（用于匹配）
            
        Returns:
            List[ExtractedEntity]: 提取的实体列表
        """
        entities = []
        
        # 1. 基于模式的实体提取
        pattern_entities = self._extract_by_patterns(text)
        entities.extend(pattern_entities)
        
        # 2. 与KG实体匹配
        if kg_entities:
            kg_matched = self._match_kg_entities(text, kg_entities)
            entities.extend(kg_matched)
        
        # 3. 去重和排序
        entities = self._deduplicate_entities(entities)
        
        return entities
    
    def _extract_by_patterns(self, text: str) -> List[ExtractedEntity]:
        """基于正则模式提取实体"""
        entities = []
        
        for entity_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                
                for match in matches:
                    entity = ExtractedEntity(
                        text=match.group(),
                        start_pos=match.start(),
                        end_pos=match.end(),
                        entity_type=entity_type,
                        confidence=0.6  # 基于模式的置信度较低
                    )
                    entities.append(entity)
        
        return entities
    
    def _match_kg_entities(self, text: str, kg_entities: List[Dict[str, Any]]) -> List[ExtractedEntity]:
        """与知识图谱实体匹配"""
        entities = []
        text_lower = text.lower()
        
        for kg_entity in kg_entities:
            entity_name = kg_entity.get("name", "")
            entity_id = kg_entity.get("id", "")
            entity_type = kg_entity.get("type", "ENTITY")
            
            if not entity_name:
                continue
            
            # 精确匹配
            if entity_name.lower() in text_lower:
                start_pos = text_lower.find(entity_name.lower())
                if start_pos != -1:
                    entity = ExtractedEntity(
                        text=entity_name,
                        start_pos=start_pos,
                        end_pos=start_pos + len(entity_name),
                        entity_type=entity_type,
                        confidence=0.9,  # KG匹配置信度较高
                        kg_entity_id=entity_id
                    )
                    entities.append(entity)
            
            # 检查别名匹配
            aliases = kg_entity.get("aliases", [])
            for alias in aliases:
                if alias.lower() in text_lower:
                    start_pos = text_lower.find(alias.lower())
                    if start_pos != -1:
                        entity = ExtractedEntity(
                            text=alias,
                            start_pos=start_pos,
                            end_pos=start_pos + len(alias),
                            entity_type=entity_type,
                            confidence=0.8,  # 别名匹配置信度中等
                            kg_entity_id=entity_id
                        )
                        entities.append(entity)
        
        return entities
    
    def _deduplicate_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """去重实体（保留置信度最高的）"""
        # 按位置分组
        position_groups = {}
        
        for entity in entities:
            key = (entity.start_pos, entity.end_pos)
            if key not in position_groups:
                position_groups[key] = []
            position_groups[key].append(entity)
        
        # 每个位置保留置信度最高的实体
        deduplicated = []
        for group in position_groups.values():
            best_entity = max(group, key=lambda e: e.confidence)
            deduplicated.append(best_entity)
        
        # 按位置排序
        deduplicated.sort(key=lambda e: e.start_pos)
        
        return deduplicated
    
    def extract_entities_with_kg_context(self, text: str, neo4j_client) -> Tuple[List[ExtractedEntity], List[str]]:
        """
        提取实体并返回相关的KG实体ID
        
        Args:
            text: 输入文本
            neo4j_client: Neo4j客户端
            
        Returns:
            Tuple[List[ExtractedEntity], List[str]]: (提取的实体, KG实体ID列表)
        """
        try:
            # 1. 从KG获取所有实体（可以优化为只获取相关实体）
            kg_entities = self._get_kg_entities(neo4j_client)
            
            # 2. 提取实体
            entities = self.extract_entities(text, kg_entities)
            
            # 3. 收集KG实体ID
            kg_entity_ids = []
            for entity in entities:
                if entity.kg_entity_id:
                    kg_entity_ids.append(entity.kg_entity_id)
            
            return entities, list(set(kg_entity_ids))  # 去重
            
        except Exception as e:
            self.logger.error(f"实体提取失败: {e}")
            return [], []
    
    def _get_kg_entities(self, neo4j_client, limit: int = 1000) -> List[Dict[str, Any]]:
        """从KG获取实体（可以缓存优化）"""
        try:
            cypher = """
            MATCH (e:Entity)
            RETURN e.id as id, 
                   e.name as name, 
                   e.type as type,
                   e.aliases as aliases
            LIMIT $limit
            """
            
            params = {"limit": limit}
            result = neo4j_client.execute_cypher(cypher, params)
            
            return result or []
            
        except Exception as e:
            self.logger.error(f"获取KG实体失败: {e}")
            return []
    
    def get_entity_statistics(self, entities: List[ExtractedEntity]) -> Dict[str, Any]:
        """获取实体提取统计信息"""
        stats = {
            "total_entities": len(entities),
            "entity_types": {},
            "kg_matched": 0,
            "avg_confidence": 0.0
        }
        
        if not entities:
            return stats
        
        total_confidence = 0.0
        
        for entity in entities:
            # 类型统计
            entity_type = entity.entity_type
            if entity_type not in stats["entity_types"]:
                stats["entity_types"][entity_type] = 0
            stats["entity_types"][entity_type] += 1
            
            # KG匹配统计
            if entity.kg_entity_id:
                stats["kg_matched"] += 1
            
            total_confidence += entity.confidence
        
        stats["avg_confidence"] = total_confidence / len(entities)
        
        return stats