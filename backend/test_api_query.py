#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试知识图谱查询 API
"""

import requests
import json

def test_book_graph(book_id: str = "book:交付:de78900c"):
    """测试获取书籍图谱API"""
    url = f"http://localhost:8000/api/v1/kg/books/{book_id}"
    
    print("=" * 80)
    print(f"测试知识图谱查询 API")
    print("=" * 80)
    print(f"URL: {url}")
    print("-" * 80)
    
    try:
        response = requests.get(url, timeout=10)
        
        print(f"\n状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ 查询成功！")
            print(f"\n返回数据:")
            print(f"  - 节点数量: {len(data.get('nodes', []))}")
            print(f"  - 边数量: {len(data.get('edges', []))}")
            
            # 显示前几个节点
            nodes = data.get('nodes', [])
            if nodes:
                print(f"\n前5个节点:")
                for i, node in enumerate(nodes[:5], 1):
                    print(f"  {i}. ID: {node.get('id')}")
                    print(f"     Name: {node.get('name')}")
                    print(f"     Labels: {node.get('labels')}")
                    print()
            
            # 显示前几条边
            edges = data.get('edges', [])
            if edges:
                print(f"前5条边:")
                for i, edge in enumerate(edges[:5], 1):
                    source_id = edge.get('source_id') or edge.get('source')
                    target_id = edge.get('target_id') or edge.get('target')
                    edge_type = edge.get('type')
                    print(f"  {i}. {source_id} --[{edge_type}]-> {target_id}")
                    print()
        else:
            print(f"\n❌ 查询失败")
            print(f"响应内容: {response.text}")
            
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)

if __name__ == "__main__":
    import sys
    book_id = sys.argv[1] if len(sys.argv) > 1 else "book:交付:de78900c"
    test_book_graph(book_id)

