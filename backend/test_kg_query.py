#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试知识图谱查询
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.core.settings import get_settings
from app.domain.kg.builder import KGBuilder

def test_query(topic: str = "交付", query: str = "什么是交付？"):
    """测试知识图谱查询"""
    settings = get_settings()
    builder = KGBuilder(settings)
    
    print("=" * 80)
    print(f"测试知识图谱查询")
    print("=" * 80)
    print(f"书籍主题: {topic}")
    print(f"查询问题: {query}")
    print("-" * 80)
    
    try:
        # 调用 query 方法
        result = builder.query(topic=topic, query=query)
        
        print(f"\n✅ 查询成功！")
        print(f"\n返回结果:")
        print("-" * 80)
        print(result)
        print("-" * 80)
        
    except Exception as e:
        print(f"\n❌ 查询失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    # 可以通过命令行参数指定
    topic = sys.argv[1] if len(sys.argv) > 1 else "交付"
    query = sys.argv[2] if len(sys.argv) > 2 else "什么是交付？"
    test_query(topic, query)







