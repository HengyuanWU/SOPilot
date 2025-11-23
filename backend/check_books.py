#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库中有哪些书籍
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.infrastructure.graph_store.neo4j_store import create_neo4j_store

def check_books():
    """检查数据库中的书籍"""
    store = create_neo4j_store()
    
    if not store:
        print("❌ 无法连接到 Neo4j")
        return
    
    print("=" * 80)
    print("数据库中的书籍信息")
    print("=" * 80)
    
    # 检查所有 book: 开头的 scope
    query = """
    MATCH ()-[r]->()
    WHERE r.scope STARTS WITH 'book:'
    RETURN DISTINCT r.scope AS book_id, count(r) AS edge_count
    ORDER BY edge_count DESC
    """
    results = store.client.execute_cypher(query)
    
    if results:
        print(f"\n找到 {len(results)} 本书:\n")
        for r in results:
            book_id = r.get('book_id', '')
            edge_count = r.get('edge_count', 0)
            
            # 解析 book_id
            parts = book_id.split(':')
            if len(parts) >= 2:
                book_name = parts[1]
                print(f"  📚 书名: {book_name}")
                print(f"     book_id: {book_id}")
                print(f"     边数量: {edge_count}")
                print()
    else:
        print("\n❌ 没有找到任何书籍")
    
    # 检查所有的 Chunk 节点（代表已上传的文档）
    print("\n" + "=" * 80)
    print("数据库中的文档信息 (Chunk 节点)")
    print("=" * 80)
    
    query_chunks = """
    MATCH (c:Chunk)
    RETURN c.book_name AS book_name, c.book_id AS book_id, count(c) AS chunk_count
    ORDER BY chunk_count DESC
    """
    chunks = store.client.execute_cypher(query_chunks)
    
    if chunks:
        print(f"\n找到 {len(chunks)} 本文档:\n")
        for c in chunks:
            book_name = c.get('book_name', 'Unknown')
            book_id = c.get('book_id', 'Unknown')
            chunk_count = c.get('chunk_count', 0)
            print(f"  📄 书名: {book_name}")
            print(f"     book_id: {book_id}")
            print(f"     chunk 数量: {chunk_count}")
            print()
    else:
        print("\n❌ 没有找到任何文档 chunk")
    
    print("=" * 80)

if __name__ == "__main__":
    check_books()







