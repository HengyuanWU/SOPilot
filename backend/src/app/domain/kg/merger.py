#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
整书合并器（按IMPROOVE_GUIDE.md规范）
- 生成 book_id = book:{slug(topic)}:{md5(topic)[:8]}
- 删除旧 scope=book_id 的全部关系
- 汇总 Section 关系 → 写入 Book Scope（语义边，按 (type, source, target) 聚合）
- 节点去重合并（新增）：按 name 去重，合并元数据，重定向关系
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from typing import Dict, List, Tuple

from app.infrastructure.graph_store.neomodel_store import Neo4jStore

from .idempotent import IdGen

__all__ = ["BookMerger"]

logger = logging.getLogger(__name__)

# 关系类型枚举
RELATION_TYPES = [
    "DEFINES",
    "EXPLAINS",
    "REQUIRES",
    "SIMILAR_TO",
    "CONTRASTS_WITH",
    "IMPLEMENTS",
    "PART_OF",
]


class BookMerger:
    """整书级别的图谱合并器。"""

    def __init__(self, settings):
        """初始化合并器。
        
        Args:
            settings: 应用配置对象
        """
        self.settings = settings
        self.idgen = IdGen(settings)
        self.use_apoc = getattr(settings, "NEO4J_USE_APOC", False)
        self.batch_size = getattr(settings, "KG_TX_BATCH_SIZE", 100)
    
    def _validate_rel_type(self, raw: str) -> str:
        """關係型別白名單/正則校驗，避免注入風險。"""
        allowed = {"HAS_CHUNK", "MENTIONS", "RELATED", "RELATED_TO", "PART_OF", "INSTANCE_OF",
                   "DEFINES", "EXPLAINS", "REQUIRES", "SIMILAR_TO", "CONTRASTS_WITH", "IMPLEMENTS"}
        name = str(raw or "RELATED").strip().upper()
        if name in allowed:
            return name
        import re as _re  # noqa: PLC0415
        if _re.match(r"^[A-Z_][A-Z0-9_]*$", name):
            return name
        logger.warning(f"非法关系类型'{name}'，回退為 'RELATED'")
        return "RELATED"
    
    def merge_book(self, topic: str) -> str:
        """合并整书图谱。
        
        Args:
            topic: 书籍主题
            
        Returns:
            book_id
        """
        # 生成book_id
        slug = self.idgen._slugify(topic)
        topic_hash = hashlib.md5(topic.encode()).hexdigest()[:8]
        book_id = f"book:{slug}:{topic_hash}"
        
        # 新增：节点去重合并（在关系聚合之前）
        try:
            node_mapping = self.consolidate_nodes(book_id)
            merged_count = len([k for k, v in node_mapping.items() if k != v])
            logger.info(f"节点合并完成: {merged_count} 个重复节点已去重")
        except Exception as e:
            logger.error(f"节点合并失败: {e}", exc_info=True)
            # 失败不影响后续流程
        
        # 删除旧的book级关系
        self._delete_book_edges(book_id)
        
        # 汇总并写入book级关系
        self._aggregate_book_relations(book_id)
        
        return book_id
    
    def consolidate_nodes(self, book_id: str, section_ids: List[str] = None) -> Dict[str, any]:
        """节点去重合并（新增方法）。
        
        步骤：
        1. 查询所有 Concept 节点（可选：仅查询特定 section 相关的节点）
        2. 按 name.lower() 分组，生成节点映射表
        3. 合并元数据到 canonical 节点
        4. 批量更新关系端点
        5. 删除冗余节点
        
        Args:
            book_id: 书籍ID（用于日志）
            section_ids: 可选的 section ID 列表，用于过滤节点范围
            
        Returns:
            结果字典，包含：
            - success: bool - 是否成功
            - node_mapping: Dict[str, str] - {old_id: canonical_id} 映射表
            - merged_count: int - 合并的节点组数
            - error: str - 错误信息（如果失败）
        """
        logger.info(f"开始节点去重合并 (book_id={book_id}, section_count={len(section_ids) if section_ids else 'all'})")
        
        try:
            # 1. 查询所有 Concept 节点
            nodes = self._fetch_all_concepts(section_ids)
            if not nodes:
                logger.info("没有找到任何 Concept 节点，跳过合并")
                return {
                    "success": True,
                    "node_mapping": {},
                    "merged_count": 0,
                    "total_nodes": 0,
                }
            
            logger.info(f"查询到 {len(nodes)} 个 Concept 节点")
            
            # 2. 生成节点映射表
            node_mapping = self._create_node_mapping(nodes)
            
            # 统计合并的节点组数
            merged_count = len(set(node_mapping.values()))
            duplicate_count = len(node_mapping) - merged_count
            
            logger.info(f"节点映射生成完成: {merged_count} 个唯一节点, {duplicate_count} 个重复节点")
            
            # 3. 合并元数据
            self._merge_metadata(node_mapping, nodes)
            
            # 4. 批量更新关系端点
            self._update_edges_batch(node_mapping)
            
            # 5. 删除冗余节点
            self._delete_redundant_nodes(node_mapping)
            
            logger.info(f"节点去重合并完成: 合并了 {duplicate_count} 个重复节点")
            
            return {
                "success": True,
                "node_mapping": node_mapping,
                "merged_count": merged_count,
                "total_nodes": len(nodes),
                "duplicate_count": duplicate_count,
            }
            
        except Exception as e:
            logger.error(f"节点合并失败: {e}", exc_info=True)
            return {
                "success": False,
                "node_mapping": {},
                "merged_count": 0,
                "error": str(e),
            }

    def _delete_book_edges(self, book_id: str) -> None:
        """删除book的旧边。
        
        Args:
            book_id: 书籍ID
        """
        cypher = "MATCH ()-[r]-() WHERE r.scope = $scope DELETE r"
        Neo4jStore.run_cypher(cypher, {"scope": book_id})

    def _aggregate_book_relations(self, book_id: str) -> None:
        """汇总section关系为book关系。
        
        Args:
            book_id: 书籍ID
        """
        if self.use_apoc:
            # 使用APOC版本
            self._aggregate_with_apoc(book_id)
        else:
            # 不使用APOC版本
            self._aggregate_without_apoc(book_id)

    def _aggregate_with_apoc(self, book_id: str) -> None:
        """使用APOC聚合关系。
        
        Args:
            book_id: 书籍ID
        """
        cypher_template = """
        MATCH (s)-[r:%s]-(t) WHERE r.src IS NOT NULL AND r.src <> '__book_merge__'
        WITH DISTINCT type(r) AS typ, s.id AS sid, t.id AS tid
        WITH typ, sid, tid, $scope AS scope
        WITH typ, sid, tid, scope, toLower(typ) + '|' + sid + '|' + tid + '|' + scope AS sig
        WITH typ, sid, tid, scope, right(toHex(apoc.util.md5(sig)),16) AS rid
        MATCH (ss {id:sid}), (tt {id:tid})
        MERGE (ss)-[e:%s {rid:rid}]->(tt)
        SET e.type=typ, e.src='__book_merge__', e.scope=scope, 
            e.confidence=1.0, e.weight=1.0, 
            e.created_at=coalesce(e.created_at, datetime())
        """
        
        for typ in RELATION_TYPES:
            safe_typ = self._validate_rel_type(typ)
            cypher = cypher_template % (safe_typ, safe_typ)
            try:
                Neo4jStore.run_cypher(cypher, {"scope": book_id})
            except Exception:
                # APOC不可用，回退到非APOC版本
                self.use_apoc = False
                self._aggregate_without_apoc(book_id)
                break

    def _aggregate_without_apoc(self, book_id: str) -> None:
        """不使用APOC聚合关系。
        
        Args:
            book_id: 书籍ID
        """
        # 查询所有section级关系（排除已经是book级的关系）
        cypher_query = """
        MATCH (s)-[r]-(t) 
        WHERE r.src IS NOT NULL AND r.src <> '__book_merge__'
        RETURN DISTINCT type(r) AS typ, s.id AS sid, t.id AS tid
        """
        
        results = Neo4jStore.run_cypher(cypher_query)
        
        # 按(typ, sid, tid)去重并生成rid
        unique_rels = {}
        for row in results:
            key = (row["typ"], row["sid"], row["tid"])
            if key not in unique_rels:
                # 生成rid
                rid_str = f"{row['typ']}|{row['sid']}|{row['tid']}|{book_id}"
                rid = hashlib.md5(rid_str.encode()).hexdigest()[:16]
                unique_rels[key] = {
                    "typ": row["typ"],
                    "sid": row["sid"],
                    "tid": row["tid"],
                    "rid": rid,
                }
        
        # 批量创建book级关系
        for rel in unique_rels.values():
            self._create_book_relation(rel, book_id)

    def _create_book_relation(self, rel: dict, book_id: str) -> None:
        """创建单个book级关系。
        
        Args:
            rel: 关系数据
            book_id: 书籍ID
        """
        # 动态构建Cypher（关系类型作为标签）
        safe_typ = self._validate_rel_type(rel['typ'])
        cypher = f"""
        MATCH (ss {{id:$sid}}), (tt {{id:$tid}})
        MERGE (ss)-[e:{safe_typ} {{rid:$rid}}]->(tt)
        SET e.type=$typ, e.src='__book_merge__', e.scope=$scope,
            e.confidence=1.0, e.weight=1.0,
            e.created_at=coalesce(e.created_at, datetime())
        """
        
        params = {
            "sid": rel["sid"],
            "tid": rel["tid"],
            "rid": rel["rid"],
            "typ": rel["typ"],
            "scope": book_id,
        }
        
        Neo4jStore.run_cypher(cypher, params)
    
    # ========== 节点去重辅助方法 ==========
    
    def _fetch_all_concepts(self, section_ids: List[str] = None) -> List[Dict]:
        """查询所有 Concept 节点。
        
        Args:
            section_ids: 可选的 section ID 列表，用于过滤节点范围
            
        Returns:
            节点列表，每个节点包含 {id, name, aliases, desc}
        """
        # 如果提供了 section_ids，则通过关系过滤节点
        # 这样可以只处理与特定 section 相关的节点，提升性能
        if section_ids:
            query = """
            MATCH (n:Concept)-[r]-()
            WHERE r.scope IN $section_ids OR r.src IN $section_ids
            RETURN DISTINCT n.id AS id, n.name AS name, 
                   n.aliases AS aliases, n.desc AS desc
            """
            params = {"section_ids": section_ids}
        else:
            # 查询所有 Concept 节点
            query = """
            MATCH (n:Concept)
            RETURN n.id AS id, n.name AS name, 
                   n.aliases AS aliases, n.desc AS desc
            """
            params = {}
        
        try:
            results = Neo4jStore.run_cypher(query, params)
            return results
        except Exception as e:
            logger.error(f"查询 Concept 节点失败: {e}", exc_info=True)
            raise  # 重新抛出异常，让上层处理
    
    def _create_node_mapping(self, nodes: List[Dict]) -> Dict[str, str]:
        """创建节点映射表。
        
        按 name.lower() 分组，对每组选择 ID 最小的节点作为 canonical。
        
        Args:
            nodes: 节点列表
            
        Returns:
            映射表 {old_id: canonical_id}
        """
        # 按 name.lower() 分组
        groups = defaultdict(list)
        for node in nodes:
            name = node.get("name", "").strip()
            if not name:
                continue
            # 使用 lower() 实现大小写不敏感的去重
            key = name.lower()
            groups[key].append(node)
        
        # 生成映射表
        mapping = {}
        duplicate_count = 0
        
        for name_key, group in groups.items():
            if len(group) == 1:
                # 单个节点，映射到自己
                node = group[0]
                mapping[node["id"]] = node["id"]
            else:
                # 多个重复节点，选择 ID 最小的作为 canonical
                canonical_node = min(group, key=lambda n: n["id"])
                canonical_id = canonical_node["id"]
                
                for node in group:
                    mapping[node["id"]] = canonical_id
                    if node["id"] != canonical_id:
                        duplicate_count += 1
        
        logger.info(f"节点映射表生成完成: {len(groups)} 个唯一概念, {duplicate_count} 个重复节点")
        return mapping
    
    def _merge_metadata(self, node_mapping: Dict[str, str], nodes: List[Dict]) -> None:
        """合并元数据到 canonical 节点。
        
        合并策略：
        - aliases: 合并所有重复节点的别名（去重）
        - desc: 选择最长的描述
        
        Args:
            node_mapping: 节点映射表
            nodes: 原始节点列表
        """
        # 按 canonical_id 分组节点
        canonical_groups = defaultdict(list)
        for node in nodes:
            node_id = node["id"]
            canonical_id = node_mapping.get(node_id, node_id)
            canonical_groups[canonical_id].append(node)
        
        # 为每个 canonical 节点合并元数据
        queries = []
        for canonical_id, group in canonical_groups.items():
            if len(group) == 1:
                # 单个节点，无需合并
                continue
            
            # 合并 aliases（去重）
            all_aliases = set()
            for node in group:
                aliases = node.get("aliases", []) or []
                if isinstance(aliases, list):
                    all_aliases.update(aliases)
            
            # 选择最长的 desc
            descs = [node.get("desc", "") or "" for node in group]
            longest_desc = max(descs, key=len) if descs else ""
            
            # 更新 canonical 节点
            cypher = """
            MATCH (n:Concept {id: $id})
            SET n.aliases = $aliases, n.desc = $desc, n.updated_at = datetime()
            """
            params = {
                "id": canonical_id,
                "aliases": list(all_aliases),
                "desc": longest_desc[:2048],  # 限制长度
            }
            queries.append((cypher, params))
        
        # 批量执行更新
        if queries:
            try:
                Neo4jStore.run_tx(queries)
                logger.info(f"元数据合并完成: {len(queries)} 个 canonical 节点已更新")
            except Exception as e:
                logger.error(f"元数据合并失败: {e}", exc_info=True)
    
    def _update_edges_batch(self, node_mapping: Dict[str, str]) -> None:
        """批量更新关系端点。
        
        对于每个需要重定向的节点，将其所有关系重定向到 canonical 节点。
        
        Args:
            node_mapping: 节点映射表
        """
        # 筛选需要处理的节点（old_id != canonical_id）
        nodes_to_redirect = [
            (old_id, new_id) 
            for old_id, new_id in node_mapping.items() 
            if old_id != new_id
        ]
        
        if not nodes_to_redirect:
            logger.info("没有需要重定向的关系")
            return
        
        logger.info(f"开始批量更新关系: {len(nodes_to_redirect)} 个节点需要重定向")
        
        # 分批处理
        total_updated = 0
        batch_size = self.batch_size
        
        for i in range(0, len(nodes_to_redirect), batch_size):
            batch = nodes_to_redirect[i:i+batch_size]
            
            # 分两步处理：1) 收集关系信息 2) 重建关系
            try:
                # 步骤1：收集所有需要重定向的关系
                query_collect = """
                UNWIND $mappings AS map
                MATCH (old {id: map.old_id})
                
                // 收集出边 old -> other
                OPTIONAL MATCH (old)-[r_out]->(other)
                WHERE other.id <> map.new_id
                
                // 收集入边 other -> old
                OPTIONAL MATCH (other2)-[r_in]->(old)
                WHERE other2.id <> map.new_id
                
                RETURN map.old_id AS old_id, map.new_id AS new_id,
                       collect(DISTINCT {
                           rid: r_out.rid, type: type(r_out), props: properties(r_out), 
                           target_id: other.id, direction: 'OUT'
                       }) AS out_rels,
                       collect(DISTINCT {
                           rid: r_in.rid, type: type(r_in), props: properties(r_in), 
                           source_id: other2.id, direction: 'IN'
                       }) AS in_rels
                """
                params_collect = {
                    "mappings": [{"old_id": old, "new_id": new} for old, new in batch]
                }
                
                relations_data = Neo4jStore.run_cypher(query_collect, params_collect)
                
                # 步骤2：基于收集的信息重建关系
                rebuild_queries = []
                
                for data in relations_data:
                    old_id = data["old_id"]
                    new_id = data["new_id"]
                    out_rels = [r for r in data.get("out_rels", []) if r.get("rid")]
                    in_rels = [r for r in data.get("in_rels", []) if r.get("rid")]
                    
                    # 重建出边
                    for rel in out_rels:
                        cypher_out = f"""
                        MATCH (new {{id: $new_id}}), (target {{id: $target_id}})
                        MATCH (old {{id: $old_id}})-[r:{rel['type']}]->(target)
                        WHERE r.rid = $rid
                        MERGE (new)-[new_r:{rel['type']} {{rid: $rid}}]->(target)
                        SET new_r = $props
                        DELETE r
                        """
                        rebuild_queries.append((cypher_out, {
                            "new_id": new_id, "old_id": old_id, "target_id": rel["target_id"],
                            "rid": rel["rid"], "props": rel["props"]
                        }))
                    
                    # 重建入边
                    for rel in in_rels:
                        cypher_in = f"""
                        MATCH (new {{id: $new_id}}), (source {{id: $source_id}})
                        MATCH (source)-[r:{self._validate_rel_type(rel['type'])}]->(old {{id: $old_id}})
                        WHERE r.rid = $rid
                        MERGE (source)-[new_r:{self._validate_rel_type(rel['type'])} {{rid: $rid}}]->(new)
                        SET new_r = $props
                        DELETE r
                        """
                        rebuild_queries.append((cypher_in, {
                            "new_id": new_id, "old_id": old_id, "source_id": rel["source_id"],
                            "rid": rel["rid"], "props": rel["props"]
                        }))
                
                # 批量执行关系重建
                if rebuild_queries:
                    Neo4jStore.run_tx(rebuild_queries)
                    total_updated += len(rebuild_queries)
                    logger.info(f"批次 {i//batch_size + 1}: 已重建 {len(rebuild_queries)} 个关系")
                
            except Exception as e:
                logger.error(f"批次 {i//batch_size + 1} 关系更新失败: {e}", exc_info=True)
                # 继续处理剩余批次
        
        logger.info(f"关系重定向完成: 共处理 {total_updated} 个关系")
    
    def _delete_redundant_nodes(self, node_mapping: Dict[str, str]) -> None:
        """批量删除冗余节点。
        
        删除所有已被重定向的节点（old_id != canonical_id 的节点）。
        
        Args:
            node_mapping: 节点映射表
        """
        # 筛选需要删除的节点
        nodes_to_delete = [
            old_id 
            for old_id, new_id in node_mapping.items() 
            if old_id != new_id
        ]
        
        if not nodes_to_delete:
            logger.info("没有需要删除的冗余节点")
            return
        
        logger.info(f"开始批量删除冗余节点: {len(nodes_to_delete)} 个节点")
        
        # 分批删除
        total_deleted = 0
        batch_size = self.batch_size
        
        for i in range(0, len(nodes_to_delete), batch_size):
            batch = nodes_to_delete[i:i+batch_size]
            
            try:
                cypher = """
                UNWIND $node_ids AS node_id
                MATCH (n {id: node_id})
                DELETE n
                RETURN count(n) AS deleted
                """
                params = {"node_ids": batch}
                
                results = Neo4jStore.run_cypher(cypher, params)
                batch_deleted = sum(r.get("deleted", 0) for r in results)
                total_deleted += batch_deleted
                
                logger.info(f"批次 {i//batch_size + 1}: 已删除 {batch_deleted} 个节点")
                
            except Exception as e:
                logger.error(f"批次 {i//batch_size + 1} 节点删除失败: {e}", exc_info=True)
                # 继续处理剩余批次
        
        logger.info(f"冗余节点删除完成: 共删除 {total_deleted} 个节点")
