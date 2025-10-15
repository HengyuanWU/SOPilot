# KG 404 Issue - 诊断与解决方案

## 问题描述

前端请求 `GET /api/v1/kg/books/book:测试:d8a1fa8d` 返回 404 错误：
```json
{"detail":"未找到书籍知识图谱: book:测试:d8a1fa8d"}
```

## 根本原因

通过分析Docker日志和Neo4j数据库，发现：

### 1. Neo4j数据库为空
```bash
docker exec sopilot-neo4j cypher-shell -u neo4j -p test1234 -d neo4j "MATCH (n) RETURN count(n);"
# 结果: node_count = 0

docker exec sopilot-neo4j cypher-shell -u neo4j -p test1234 -d neo4j "MATCH ()-[r]->() RETURN count(r);"
# 结果: edge_count = 0
```

### 2. Docker日志显示
```
2025-10-04 16:31:13,862 INFO app.domain.workflows.textbook.nodes.book_graph_node | 从section bffddd03523f 读取到 0 条边
2025-10-04 16:31:13,866 INFO app.domain.workflows.textbook.nodes.book_graph_node | 从section 26b6c69e635d 读取到 0 条边
...
2025-10-04 16:31:13,879 INFO app.domain.workflows.textbook.nodes.book_graph_node | 总共读取到 0 条section边数据
2025-10-04 16:31:13,879 INFO app.domain.workflows.textbook.nodes.book_graph_node | 整本书图谱存储完成: 0 节点, 0 边
```

### 3. Neo4j警告信息
```
WARNING neo4j.notifications | Received notification from DBMS server: 
{severity: WARNING} {code: Neo.ClientNotification.Statement.UnknownPropertyKeyWarning}
{title: The provided property key is not in the database}
{description: One of the property names in your query is not available in the database
 (the missing property name is: scope/source_id/target_id/weight/desc)}
```

## 问题分析

1. **没有KG数据被存储**: workflow执行了，但每个section返回0条边，说明：
   - LLM抽取阶段可能没有提取到实体和关系
   - 或者数据没有成功写入Neo4j
   - 或者输入内容为空/太短

2. **属性不匹配**: Neo4j警告缺少 `scope`, `source_id`, `target_id` 等属性
   - 查询时使用 `r.scope`, `r.source_id`, `r.target_id`
   - 但这些属性在存储时可能没有正确设置

3. **book_graph_node的逻辑**:
   - 尝试从section数据中读取边
   - 将这些边重新标记为book scope
   - 但由于section数据为空，所以book数据也为空

## 可能原因

### A. KG抽取失败 (最可能)
- spaCy模型未安装或初始化失败
- LLM调用失败（API key、网络问题）
- 内容太短或格式不正确
- 置信度阈值过高导致数据被过滤

### B. Neo4j存储失败
- 连接问题（已排除，因为能连接查询）
- 事务失败但没有报错
- merge_edge方法有bug

### C. workflow配置问题
- KG_ENABLED设置为false
- 使用了mock数据而不是真实workflow

## 检查步骤

### 1. 检查spaCy模型
```python
import spacy
try:
    nlp = spacy.load("zh_core_web_sm")
    print("✅ spaCy中文模型已安装")
except OSError:
    print("❌ spaCy中文模型未安装")
    print("请运行: python -m spacy download zh_core_web_sm")
```

### 2. 检查LLM配置
查看环境变量中是否配置了API密钥：
- `APP_DEFAULT_PROVIDER`
- `APP_PROVIDERS__<PROVIDER>__API_KEYS`

### 3. 检查workflow日志
查找KG抽取的详细日志：
```bash
docker logs sopilot-backend 2>&1 | grep -i "kg\|builder\|normalizer\|store"
```

### 4. 检查settings
```python
from app.core.settings import get_settings
settings = get_settings()
print(f"KG_ENABLED: {settings.KG_ENABLED}")
print(f"KG_LANGUAGE: {settings.KG_LANGUAGE}")
print(f"use_real_workflow: {settings.use_real_workflow}")
```

## 解决方案

### 方案1: 安装spaCy模型（如果缺失）

```bash
# 进入backend容器
docker exec -it sopilot-backend bash

# 安装中文模型
python -m spacy download zh_core_web_sm

# 重启容器
docker-compose restart backend
```

### 方案2: 检查和修复LLM配置

在 `.env` 或 `docker-compose.yml` 中添加：
```yaml
environment:
  - APP_DEFAULT_PROVIDER=siliconflow
  - APP_PROVIDERS__SILICONFLOW__API_KEYS=["sk-your-api-key"]
  - APP_PROVIDERS__SILICONFLOW__MODEL=deepseek-ai/DeepSeek-V3
  - APP_USE_REAL_WORKFLOW=true
```

### 方案3: 降低置信度阈值

在settings中设置更低的阈值：
```python
KG_CONFIDENCE_ENTITY_MIN: float = 0.3  # 降低到0.3
KG_CONFIDENCE_RELATION_MIN: float = 0.3  # 降低到0.3
```

### 方案4: 添加调试日志

修改 `backend/src/app/domain/kg/pipeline.py`:
```python
def _store_kg(self, kg: KGDict, section_id: str) -> Dict[str, Any]:
    self.logger.info(f"准备存储KG: {kg.total_nodes}节点, {kg.total_edges}边")
    
    # 添加详细日志
    for i, node in enumerate(kg.nodes[:5]):  # 打印前5个节点
        self.logger.info(f"节点{i}: {node.id} - {node.name}")
    
    for i, edge in enumerate(kg.edges[:5]):  # 打印前5条边
        self.logger.info(f"边{i}: {edge.source} -> {edge.target} ({edge.type})")
```

### 方案5: 重新运行workflow

1. 清空Neo4j数据库：
```bash
docker exec sopilot-neo4j cypher-shell -u neo4j -p test1234 -d neo4j "MATCH (n) DETACH DELETE n;"
```

2. 重新运行textbook workflow

3. 检查日志确认数据被正确存储

## 临时验证步骤

创建测试脚本验证KG抽取功能：

```python
# scripts/test_kg_extraction.py
from app.domain.kg.pipeline import KGPipeline
from app.domain.kg.schemas import KGPipelineInput
from app.infrastructure.graph_store import create_neo4j_store
from app.core.settings import get_settings

settings = get_settings()
store = create_neo4j_store()

pipeline = KGPipeline(store, settings)

# 测试简单内容
test_input = KGPipelineInput(
    topic="测试",
    chapter_title="第一章",
    subchapter_title="测试小节",
    content="Python是一种编程语言。Python由Guido van Rossum创建。Python用于数据科学和Web开发。",
    keywords=["Python", "编程语言"],
    language="zh"
)

result = pipeline.run_one_subchapter(test_input)
print(f"提取结果: {result.kg_part.get('total_nodes', 0)}节点, {result.kg_part.get('total_edges', 0)}边")
print(f"存储统计: {result.store_stats}")
```

## 下一步

1. 运行诊断脚本确认具体原因
2. 根据诊断结果应用相应解决方案
3. 重新运行workflow
4. 验证API是否返回正确数据

