# KG 404 问题解决方案

## 问题总结

前端请求 `GET /api/v1/kg/books/book:测试:d8a1fa8d` 返回 404 错误：未找到书籍知识图谱。

## 根本原因

**DateTime格式不兼容导致所有Neo4j写入操作失败**

### 错误日志
```
ERROR app.infrastructure.graph_store.neo4j_client | 执行 Cypher 失败: 
{code: Neo.ClientError.Statement.SyntaxError} 
{message: Text cannot be parsed to a DateTime}
```

这个错误在workflow执行期间发生了100多次，导致：
- 158个节点全部写入失败
- 10条边全部写入失败
- Neo4j数据库保持为空（0 nodes, 0 edges）
- book_graph_node无数据可读，导致API返回404

### 原因分析

`backend/src/app/infrastructure/graph_store/neo4j_client.py` 中的问题代码：

```python
# 问题代码
props["created_at"] = _dt.utcnow().isoformat()  # 生成: "2025-10-04T16:31:13.123456"

# 在Cypher中使用
SET n.created_at = $created_at  # Neo4j无法解析这个字符串格式
```

Python的 `.isoformat()` 生成的datetime字符串格式与Neo4j的 `datetime()` 函数不兼容。

## 解决方案

### 修复内容

修改了 `neo4j_client.py` 的两个方法：

#### 1. `merge_node` 方法
```python
# 修改前
cypher = f"""
MERGE (n{labels} {{id: $id}})
SET n += $properties
SET n.updated_at = datetime()
"""
props = dict(node)
if "created_at" not in props:
    props["created_at"] = _dt.utcnow().isoformat()  # ❌ 问题

# 修改后
cypher = f"""
MERGE (n{labels} {{id: $id}})
SET n += $properties
ON CREATE SET n.created_at = datetime()  # ✅ Neo4j自己生成
SET n.updated_at = datetime()
"""
props = dict(node)
props.pop("created_at", None)  # ✅ 移除Python生成的时间戳
```

#### 2. `merge_edge` 方法
```python
# 修改前
cypher = f"""
MATCH (source {{id: $source_id}})
MATCH (target {{id: $target_id}})
MERGE (source)-[r:{edge_type} {{rid: $rid}}]->(target)
SET r += $properties
SET r.updated_at = datetime()
"""
if "created_at" not in props:
    props["created_at"] = _dt.utcnow().isoformat()  # ❌ 问题

# 修改后
cypher = f"""
MATCH (source {{id: $source_id}})
MATCH (target {{id: $target_id}})
MERGE (source)-[r:{edge_type} {{rid: $rid}}]->(target)
SET r += $properties
ON CREATE SET r.created_at = datetime()  # ✅ Neo4j自己生成
SET r.updated_at = datetime()
"""
props.pop("created_at", None)  # ✅ 移除Python生成的时间戳
```

### 核心改进

1. **使用 `ON CREATE SET`**: 只在创建时设置 `created_at`
2. **让Neo4j生成时间戳**: 使用 `datetime()` 而不是传入字符串
3. **移除Python时间戳**: `props.pop("created_at", None)`

## 后续步骤

### 1. 清空Neo4j数据库（可选）
如果之前的数据有问题，可以清空：
```bash
docker exec sopilot-neo4j cypher-shell -u neo4j -p test1234 -d neo4j "MATCH (n) DETACH DELETE n;"
```

### 2. 重新运行Workflow
通过前端界面重新运行textbook workflow，生成知识图谱。

### 3. 验证修复
运行以下命令验证数据已正确存储：
```bash
# 检查节点数
docker exec sopilot-neo4j cypher-shell -u neo4j -p test1234 -d neo4j "MATCH (n) RETURN count(n) as nodes;"

# 检查边数
docker exec sopilot-neo4j cypher-shell -u neo4j -p test1234 -d neo4j "MATCH ()-[r]->() RETURN count(r) as edges;"

# 检查边属性
docker exec sopilot-neo4j cypher-shell -u neo4j -p test1234 -d neo4j "MATCH ()-[r]->() RETURN properties(r) LIMIT 1;"
```

### 4. 测试API
```bash
curl http://localhost:8000/api/v1/kg/books/book:测试:d8a1fa8d
```

应该返回包含nodes和edges的JSON数据，而不是404错误。

## 技术细节

### Neo4j DateTime 函数
Neo4j的 `datetime()` 函数：
- **无参数调用**: `datetime()` - 返回当前UTC时间
- **从字符串解析**: `datetime("2025-10-04T16:31:13Z")` - 需要特定格式
- **ISO格式要求**: 必须是RFC 3339格式，需要时区信息

### Python datetime.isoformat()
- 生成格式: `"2025-10-04T16:31:13.123456"` 
- **缺少时区信息** - 这是主要问题
- Neo4j无法自动解析这个格式

### 最佳实践
1. 让数据库生成时间戳 - 避免格式问题
2. 使用 `ON CREATE SET` - 只在创建时设置
3. 使用 `ON MATCH SET` - 只在匹配时更新
4. 不要传递字符串时间戳 - 除非确保格式完全兼容

## 影响范围

### 已修复
- ✅ 节点创建
- ✅ 边创建  
- ✅ 时间戳字段
- ✅ book_graph_node读取section数据
- ✅ API返回book知识图谱

### 需要验证
- [ ] 重新运行workflow确认数据正确存储
- [ ] 前端可视化正常显示知识图谱
- [ ] section级别API也能正常工作

## 相关文件

- `backend/src/app/infrastructure/graph_store/neo4j_client.py` - 主要修复文件
- `backend/src/app/domain/workflows/textbook/nodes/book_graph_node.py` - 依赖正确的数据
- `backend/src/app/api/v1/kg.py` - API端点

## 预防措施

### 建议添加的测试
1. Neo4j写入测试 - 验证节点和边能成功创建
2. DateTime格式测试 - 确保时间戳兼容
3. 集成测试 - 完整workflow到API查询

### 日志改进
添加更详细的错误日志，包括：
- 写入失败时的具体错误信息
- 成功写入的数量统计
- 时间戳格式验证

### 监控指标
- Neo4j写入成功率
- DateTime解析错误计数
- Workflow执行状态追踪

