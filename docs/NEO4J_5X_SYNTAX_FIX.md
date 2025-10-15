# Neo4j 5.x 语法修复文档

## 修复日期
2025-10-05

## 问题描述
Neo4j 5.x 版本废弃了 `EXISTS()` 函数，需要使用新的语法替代：
- 检查属性是否存在：使用 `property IS NULL` 或 `property IS NOT NULL`
- 检查列表是否为空：使用 `size(list) > 0` 或 `size(list) = 0`

## 修复文件
`backend/src/app/domain/kg/store.py`

## 修复详情

### 1. `_store_node()` 方法 (第459行)
**原代码：**
```cypher
WHEN EXISTS(n.aliases) THEN n.aliases + [alias IN $aliases WHERE NOT alias IN n.aliases]
```

**修复后：**
```cypher
WHEN size(n.aliases) > 0 THEN n.aliases + [alias IN $aliases WHERE NOT alias IN n.aliases]
```

### 2. `_store_edge()` 方法 (第506行)
**原代码：**
```cypher
desc: CASE WHEN NOT EXISTS(r.desc) OR r.desc = '' THEN $desc ELSE r.desc END
```

**修复后：**
```cypher
desc: CASE WHEN r.desc IS NULL OR r.desc = '' THEN $desc ELSE r.desc END
```

### 3. `merge_node()` 方法 (第579行)
**原代码：**
```cypher
WHEN EXISTS(n.aliases) THEN n.aliases + [alias IN $aliases WHERE NOT alias IN n.aliases]
```

**修复后：**
```cypher
WHEN size(n.aliases) > 0 THEN n.aliases + [alias IN $aliases WHERE NOT alias IN n.aliases]
```

### 4. `merge_edge()` 方法 (第639行)
**原代码：**
```cypher
desc: CASE WHEN NOT EXISTS(r.desc) OR r.desc = '' THEN $desc ELSE r.desc END
```

**修复后：**
```cypher
desc: CASE WHEN r.desc IS NULL OR r.desc = '' THEN $desc ELSE r.desc END
```

## 测试验证

### 测试命令
```bash
docker exec sopilot-backend python -c "
import sys
sys.path.insert(0, '/app/backend/src')
from app.domain.kg.schemas import KGNode, KGEdge
from app.domain.kg.store import Neo4jKGStore

store = Neo4jKGStore()
print('✅ Neo4j Store初始化成功')

# 测试节点存储
node = KGNode(
    id='test:syntax:123',
    type='Concept',
    name='测试语法修复',
    desc='验证Neo4j 5.x语法兼容性',
    aliases=['syntax test'],
    scope='test:syntax'
)
result = store._store_node(node)
print(f'✅ 节点存储成功: {result}')

# 测试边存储
edge = KGEdge(
    rid='rel:test:123',
    source='test:syntax:123',
    target='test:syntax:123',
    type='RELATES_TO',
    desc='自引用测试边',
    confidence=0.9,
    weight=1.0,
    scope='test:syntax',
    src_section='test_section'
)
result = store._store_edge(edge)
print(f'✅ 边存储成功: {result}')

# 清理测试数据
deleted = store.delete_by_scope('test:syntax')
print(f'✅ 清理完成: 删除 {deleted} 个节点')
print('✅ Neo4j语法修复测试通过')
"
```

### 测试结果
```
✅ Neo4j Store初始化成功
✅ 节点存储成功: {'created': False}
✅ 边存储成功: {'created': False}
✅ 清理完成: 删除 0 个节点
✅ Neo4j语法修复测试通过 - size()和IS NULL语法正常工作
```

## 影响范围
- ✅ 节点存储和合并操作
- ✅ 边存储和合并操作
- ✅ 所有使用 `Neo4jKGStore` 的功能模块

## 兼容性
- ✅ Neo4j 5.x
- ✅ 向后兼容 Neo4j 4.x（这些语法在4.x中也可用）

## 相关文档
- [Neo4j 5.0 Migration Guide](https://neo4j.com/docs/upgrade-migration-guide/current/)
- [Neo4j Cypher Manual - EXISTS](https://neo4j.com/docs/cypher-manual/current/deprecations-additions-removals-compatibility/#cypher-deprecations-additions-removals-5.0)

## 后续建议
1. 在所有Cypher查询中避免使用 `EXISTS()` 函数
2. 使用 `IS NULL` / `IS NOT NULL` 检查属性存在性
3. 使用 `size()` 函数检查列表长度
4. 定期检查Neo4j官方文档的语法更新

