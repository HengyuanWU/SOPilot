# neomodel 5.x 迁移指南

## 概述

本项目从 neomodel 4.x 升级到 **neomodel 5.0.1**，主要 API 变化和迁移已完成。

## 关键变化

### 1. 连接初始化方式变更

#### ❌ 旧方式（neomodel 4.x）
```python
from neomodel import db

db.set_connection(settings.NEO4J_BOLT_URL)
```

#### ✅ 新方式（neomodel 5.x）
```python
from neomodel import config

config.DATABASE_URL = settings.NEO4J_BOLT_URL
```

**原因**：neomodel 5.x 重构了连接管理，`db.set_connection()` 不再更新底层 `config.DATABASE_URL`。

### 2. 已更新文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `backend/src/app/infrastructure/graph_store/neomodel_conn.py` | ✅ | 更新为 `config.DATABASE_URL` |
| `docs/IMPROOVE_GUIDE.md` | ✅ | 更新文档和示例代码 |
| `scripts/verify_neomodel_config.py` | ✅ | 新增验证脚本 |

## 验证方法

### 方法 1: 容器内验证（推荐）

```bash
docker exec sopilot-backend python -c "
from app.core.settings import get_settings
from app.infrastructure.graph_store.neomodel_conn import init_neo4j
from neomodel import config, db

settings = get_settings()
print('初始配置:', config.DATABASE_URL)

init_neo4j(settings)
print('更新后配置:', config.DATABASE_URL)

# 验证连接
result = db.cypher_query('RETURN 1 as test')
print('连接测试:', result[0][0][0], '✓')

# 验证节点数
result = db.cypher_query('MATCH (n) RETURN count(n) as count')
print('节点数量:', result[0][0][0])
"
```

### 方法 2: 使用验证脚本

```bash
# 在项目根目录
python scripts/verify_neomodel_config.py
```

## 预期输出

```
=== 验证 neomodel 5.x 配置 ===
初始配置: bolt://neo4j:foobarbaz@localhost:7687
更新后配置: bolt://neo4j:test1234@neo4j:7687
连接测试: 1 ✓

=== 验证索引安装 ===
约束数量: 11

✅ 所有验证通过！
```

## 依赖版本

```txt
neomodel==5.0.1
```

**注意**：不要升级到 5.3.x，因为可能引入不兼容的变化。项目锁定在 5.0.1。

## 常见问题

### Q1: 连接配置未生效

**症状**：调用 `init_neo4j()` 后，`config.DATABASE_URL` 没有更新

**原因**：可能使用了旧的 `db.set_connection()` API

**解决**：确认使用 `config.DATABASE_URL = ...`

### Q2: 升级后无法连接

**症状**：`ServiceUnavailable` 或连接超时

**排查步骤**：
1. 检查 Neo4j 容器是否运行：`docker ps | grep neo4j`
2. 检查 `NEO4J_BOLT_URL` 配置是否正确
3. 验证网络连通性：`docker exec sopilot-backend nc -zv neo4j 7687`

### Q3: 索引/约束问题

**症状**：写入数据时出现约束冲突

**解决**：重新安装索引
```python
from app.infrastructure.graph_store.schema import install_schema
install_schema()
```

## 回滚方案

如果需要回滚到 neomodel 4.x：

1. 更新 `requirements.txt`：
   ```
   neomodel==4.0.8
   ```

2. 恢复 `neomodel_conn.py`：
   ```python
   from neomodel import db
   
   def init_neo4j(settings) -> None:
       db.set_connection(settings.NEO4J_BOLT_URL)
   ```

3. 更新 `IMPROOVE_GUIDE.md` 中的示例代码

## 参考资料

- [neomodel 5.x 发布说明](https://github.com/neo4j-contrib/neomodel/releases)
- [neomodel 文档](https://neomodel.readthedocs.io/)
- 项目规范：`docs/IMPROOVE_GUIDE.md`

## 变更日期

- **2025-01-10**: 完成 neomodel 5.0.1 迁移
- **2025-01-10**: 更新 IMPROOVE_GUIDE.md
- **2025-01-10**: 创建本迁移指南

---

**维护者**：SOPilot Team  
**最后更新**：2025-01-10

