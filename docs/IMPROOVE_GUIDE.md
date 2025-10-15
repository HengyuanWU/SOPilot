# Prompt Hub 改造（统一存储｜版本管理｜前端编辑）

---

## 1. Prompt 中心化与前端可视化编辑（Prompt Hub）

> 遵循三原则：**不回退/不兼容旧实现、优先官方实践、可插拔解耦**。本节仅修改 Prompt 方案；其余章节不动。你已否决 DB 方案——本节改为 **YAML 作为唯一事实来源（SoT）**，结合 Git 做版本管理与回滚。

### 1.1 结论（YAML 方案总览）

* **存储介质**：YAML 文件（Git 版本化）。
* **组织方式**：`/backend/src/app/domain/prompts/` 为根，按 Agent/Workflow/Locale 分层；所有运行期读取均来自 YAML，内存带时间戳热缓存。
* **版本化与回滚**：依赖 Git（commit 即版本）。支持在前端查看历史提交并回滚到某次提交（通过后端暴露 `git` 子命令封装）。
* **绑定模型**：通过独立的 `prompt_bindings.yaml` 将 **Agent/Workflow/Locale** → **Prompt 文件** 与 **模型名/参数** 进行声明式绑定，可即时生效。

### 1.2 目录结构（MVP）

```
backend/src/app/domain/prompts/
├── agents/
│   ├── researcher.subchapter.zh.yaml
│   ├── planner.zh.yaml
│   ├── writer.zh.yaml
│   ├── validator.zh.yaml
│   └── kg_builder.zh.yaml
├── workflows/
│   └── textbook.zh.yaml          #（可选）工作流级通用提示
├── prompt_bindings.yaml          # 绑定表（见 1.4）
└── schema.json                   # JSON Schema（前端/后端双端校验）
```

### 1.3 文件格式（与主流提供商对齐）

```yaml
# 示例：agents/researcher.subchapter.zh.yaml
id: researcher.subchapter.zh
agent: researcher
locale: zh
version: 1          # 仅作语义展示；真实版本由 Git 管
messages:
  - role: system
    content: |
      你是一位专业的教材研究员。请仅针对给定的子章节进行研究输出。
  - role: user
    content: |
      教材主题：{{ topic }}
      子章节标题：{{ subchapter_title }}
      子章节大纲：
      {{ subchapter_outline | default('(无补充大纲)') }}

      请输出：
      1) 子章节关键词（8-12个，逗号分隔）
      2) 子章节研究总结（300-600字）
      3) 关键概念（3-6个，逗号分隔）

      输出格式（严格遵守）：
      ## 子章节关键词
      关键词1, 关键词2, 关键词3, ...

      ## 子章节研究总结
      [详细的研究总结]

      ## 关键概念
      概念1, 概念2, 概念3, ...
meta:
  temperature: 0.7
  max_tokens: 1500
  placeholders: [topic, subchapter_title, subchapter_outline]
```

> 与 Dify/OpenAI Chat 接口保持一致的 **多段 messages**（system/user/...），比单字符串更标准。

### 1.4 绑定与模型选择（可被用户修改）

```yaml
# backend/src/app/domain/prompts/prompt_bindings.yaml
# 将 Agent/Workflow/Locale 绑定到具体 YAML + 模型名和参数覆盖
bindings:
  - target_type: agent            # agent | workflow | global
    target_id: researcher         # agent:researcher
    locale: zh
    prompt_file: agents/researcher.subchapter.zh.yaml
    model_ref: siliconflow:Qwen/Qwen3-Coder-30B-A3B-Instruct
    params:
      temperature: 0.6
      max_tokens: 1500

  - target_type: workflow
    target_id: textbook
    locale: zh
    prompt_file: workflows/textbook.zh.yaml
    model_ref: openai:gpt-4o-mini
    params: {}
```

* **模型名可更改**：前端在绑定面板即可切换 `provider:model`，同时覆盖参数。
* **优先级**：`agent` > `workflow` > `global`，命中第一条即用。

### 1.5 后端服务（只读 YAML + 写回 + Git 封装）

* `GET  /api/v1/prompts`：扫描目录，返回 Prompt 元数据（id/路径/locale/最后修改时间）。
* `GET  /api/v1/prompts/:path`：读取 YAML 内容（含 messages/meta）。
* `PUT  /api/v1/prompts/:path`：**保存**（写回 YAML，校验 `schema.json`，并执行 `git add/commit`）。
* `POST /api/v1/prompts/validate`：渲染校验（传变量，返回渲染后的 messages 与缺失变量）。
* `GET  /api/v1/prompt-bindings`：读取 `prompt_bindings.yaml`。
* `PUT  /api/v1/prompt-bindings`：保存绑定（写回 + commit）。
* `GET  /api/v1/prompts/history?path=...`：返回该文件 Git 历史（hash、author、date、message）。
* `POST /api/v1/prompts/rollback`：回滚到指定 commit（受保护：需额外确认参数）。

**实现要点**：

* YAML 解析：`ruamel.yaml`（保留注释与顺序）或 `PyYAML` + Round-trip writer。
* 热缓存：`mtime` + `LRU`；保存后刷新缓存。
* 安全：只允许访问 `prompts/` 子树；路径白名单校验。

### 1.6 LLM 客户端重构（配合 YAML 方案）

> 仍采用 **LLMRouter + ProviderAdapter**（工程化提升），但 **Prompt 来源改为 YAML**。

```
backend/src/app/infrastructure/llm/
├── router.py          # LLMRouter：统一 messages 调用、重试/超时/错误语义
├── adapters/
│   ├── openai.py
│   ├── siliconflow.py
│   └── deepseek.py
└── types.py
```

**Agent 调用规范：**

```python
# 1) 解析绑定
binding = prompt_service.resolve_binding(target_type='agent', target_id='researcher', locale='zh')
# 2) 读取并渲染 YAML（Jinja2 占位符）
messages, meta = prompt_service.render_yaml(binding.prompt_file, variables)
# 3) 发送至 LLMRouter
resp = llm_router.generate(
    provider=binding.provider,     # 从 model_ref 解析
    model=binding.model,
    messages=messages,
    temperature=binding.params.get('temperature', meta.get('temperature', 0.7)),
    max_tokens=binding.params.get('max_tokens', meta.get('max_tokens', 1500)),
    timeout=binding.params.get('timeout', 300),
    tags={"agent":"researcher","run_id":run_id}
)
```

* **替换旧函数**：废弃 `llm_call/llm_call_via_facade`，避免单字符串调用路径（Breaking Change）。

### 1.7 前端「Prompt Studio」（三栏，无弹窗地狱）

**路由**：`/prompts`

**布局（3-pane）**：

1. 左侧：文件树/搜索（Agent/Workflow/Locale 过滤）
2. 中间：编辑器（Monaco）—Tab：`messages` 与 `meta`；下方 Diff
3. 右侧：变量区（自动解析 `{{var}}` → 表单生成）、**模型选择器**（provider+model 搜索下拉）、绑定发布区（选择 agent/workflow/locale 并保存到 `prompt_bindings.yaml`）、预览区（实时渲染 messages）

**关键交互**：

* 「保存」→ `PUT /prompts/:path`（写回 YAML + git commit）
* 「发布到绑定」→ `PUT /prompt-bindings`
* 「查看历史」→ `GET /prompts/history?path=...`（显示提交列表，可一键回滚→ `POST /prompts/rollback`）
* 「试运行」→ `/prompts/validate` + 临时 `llm_router.generate(dry_run=true)`

### 1.8 迁移步骤（只改 Prompt 相关）

1. **抽取硬编码**：将 `app/domain/agents/**` 内所有内嵌 Prompt（如 `subchapter_prompt_template`）搬到 `agents/*.yaml`（格式如 1.3）。
2. **替换调用点**：节点改为 `prompt_service.resolve_binding()` → `render_yaml()` → `llm_router.generate()`。
3. **移除旧接口**：删除 `llm_call/llm_call_via_facade`，统一走 Router。
4. **前端落地**：新增 `/prompts` 页面与三栏交互；在绑定面板即可修改**模型名**与温度/MaxTokens（满足你第 3、4、5 点）。
5. **校验与示例**：提供 `schema.json` 与示例变量集（topic、subchapter\_title、subchapter\_outline）。

### 1.9 验收清单（Prompt Hub 专属）

* [ ] YAML Schema 校验（前后端一致）
* [ ] Prompt 文件热缓存（mtime 触发）
* [ ] 绑定解析与优先级（agent > workflow > global）
* [ ] LLMRouter 三提供商适配（OpenAI/SiliconFlow/DeepSeek）
* [ ] 前端三栏交互（编辑/发布/历史/预览/试运行）
* [ ] 迁移脚本完成（硬编码 → YAML）

1.10 后端骨架代码

backend/src/app/services/prompt_service.py

from pathlib import Path
import yaml, jinja2, time
from typing import Dict, Any, List, Tuple


class PromptService:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.cache: Dict[str, Tuple[float, Any]] = {}
        self.jinja_env = jinja2.Environment()


    def _load(self, rel_path: str) -> dict:
        path = self.base / rel_path
        mtime = path.stat().st_mtime
        cached = self.cache.get(rel_path)
        if not cached or cached[0] < mtime:
            data = yaml.safe_load(path.read_text(encoding='utf-8'))
            self.cache[rel_path] = (mtime, data)
        return self.cache[rel_path][1]


    def render_yaml(self, rel_path: str, variables: Dict[str, Any]) -> Tuple[List[dict], dict]:
        data = self._load(rel_path)
        messages = []
        for m in data.get('messages', []):
            template = self.jinja_env.from_string(m['content'])
            messages.append({"role": m['role'], "content": template.render(**variables)})
        return messages, data.get('meta', {})


    def resolve_binding(self, target_type: str, target_id: str, locale: str) -> dict:
        bindings = yaml.safe_load((self.base / 'prompt_bindings.yaml').read_text())
        for b in bindings['bindings']:
            if b['target_type']==target_type and b['target_id']==target_id and b['locale']==locale:
                provider, model = b['model_ref'].split(':',1)
                return {**b, 'provider':provider, 'model':model}
        raise ValueError(f"No binding found for {target_type}:{target_id}@{locale}")

backend/src/app/infrastructure/llm/router.py

from typing import List, Dict
from .types import LLMMessage, LLMResponse
from .adapters import openai, siliconflow, deepseek


class LLMRouter:
    def generate(self, provider: str, model: str, messages: List[Dict], temperature: float=0.7, max_tokens: int=1024, timeout: int=300, tags: Dict[str,str]=None):
        if provider=="openai":
            return openai.chat(model, messages, temperature, max_tokens, timeout)
        if provider=="siliconflow":
            return siliconflow.chat(model, messages, temperature, max_tokens, timeout)
        if provider=="deepseek":
            return deepseek.chat(model, messages, temperature, max_tokens, timeout)
        raise ValueError(f"Unsupported provider {provider}")
1.11 前端骨架代码

frontend/src/views/PromptStudio.vue

<template>
  <div class="prompt-studio">
    <aside class="sidebar">
      <ul>
        <li v-for="f in files" :key="f.id" @click="selectFile(f)">{{ f.id }}</li>
      </ul>
    </aside>
    <main class="editor">
      <MonacoEditor v-model="yamlContent" language="yaml" />
      <button @click="save">保存</button>
    </main>
    <aside class="right-panel">
      <div>
        <label>变量</label>
        <div v-for="v in placeholders" :key="v">{{v}}: <input v-model="vars[v]" /></div>
      </div>
      <div>
        <label>模型</label>
        <select v-model="binding.model_ref">
          <option v-for="m in models" :value="m">{{m}}</option>
        </select>
      </div>
      <button @click="preview">预览</button>
    </aside>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import MonacoEditor from 'vue-monaco-editor'
const files = ref([])
const yamlContent = ref('')
const placeholders = ref([])
const vars = ref({})
const models = ref(["siliconflow:Qwen/Qwen3-Coder-30B-A3B-Instruct","openai:gpt-4o-mini"])
const binding = ref({model_ref:""})
function selectFile(f:any){/*load via API*/}
function save(){/*PUT /api/v1/prompts/:path*/}
function preview(){/*POST /api/v1/prompts/validate*/}
</script>
1.12 Seed 脚本

scripts/seed_prompts.py

import os, yaml


PROMPTS = {
"agents/researcher.subchapter.zh.yaml": {
'id': 'researcher.subchapter.zh',
'agent': 'researcher',
'locale': 'zh',
'messages': [
{"role":"system", "content":"你是一位专业的教材研究员。请仅针对给定的子章节进行研究输出。"},
{"role":"user", "content": "教材主题：{{topic}}\n子章节标题：{{subchapter_title}}\n子章节大纲：\n{{subchapter_outline | default('(无补充大纲)')}}..."}
],
'meta': {"temperature":0.7,"max_tokens":1500}
}
}


for path, data in PROMPTS.items():
full_path = os.path.join("backend/src/app/domain/prompts", path)
os.makedirs(os.path.dirname(full_path), exist_ok=True)
with open(full_path, 'w', encoding='utf-8') as f:
yaml.dump(data, f, allow_unicode=True, sort_keys=False)
print("Seed prompts written.")
---

## 1.13. 改造方案

### 1.13.1 存储介质

* **MVP**：YAML 文件存储（Git 管理，开发人员可直接修改，支持 CI/CD 回滚）。
* **未来**：迁移至 DB（PostgreSQL + SQLAlchemy），支持多用户权限与历史审计。

### 1.13.2 目录结构

```
backend/src/app/domain/prompts/
├── registry.py              # Prompt Registry API
├── schemas.py               # Pydantic 模型
└── agents/
    ├── researcher.zh.yaml   # 研究员 Prompt
    ├── writer.zh.yaml       # 写作 Prompt
    ├── validator.zh.yaml    # 验证 Prompt
    └── ...
```

### 1.13.3 YAML 文件示例

```yaml
id: researcher.zh
agent: researcher
language: zh
version: 1
fields:
  system: |
    你是一位专业的教材研究员……
  user: |
    教材主题: {{ topic }}\n子章节标题: {{ subchapter_title }}\n子章节大纲: {{ subchapter_outline }}
params:
  model: Qwen/Qwen3-Coder-30B-A3B-Instruct
  max_tokens: 1500
  temperature: 0.7
```

### 1.13.4 Prompt Registry

* 加载 YAML → Pydantic 校验 → 缓存 → 提供给 Agent 使用。
* 通过 `PromptRegistry.get(agent, lang)` 获取 Prompt 与参数。
* 版本号自增，支持 `PATCH` 更新（自动生成新版本）。

### 1.13.5 LLM Client 改造

* 修改 `llm_call` 接口，支持 **Prompt + Params 统一对象**：

```python
@dataclass
class PromptConfig:
    text: str
    model: str
    max_tokens: int
    temperature: float
    provider: str

def llm_call(prompt_cfg: PromptConfig) -> str:
    request = LLMRequest(
        provider=prompt_cfg.provider,
        model=prompt_cfg.model,
        messages=[{"role": "user", "content": prompt_cfg.text}],
        temperature=prompt_cfg.temperature,
        max_tokens=prompt_cfg.max_tokens,
    )
    return facade.call(request)["content"]
```

---

## 1.14. 前端改造

### 1.14.1 新增页面

* `PromptStudio.vue`：集中管理所有 Agent Prompt。
* 功能：

  * 列表查看（Agent/语言/模型名/版本）
  * 点击进入详情编辑（支持多段编辑：system/user/tool）
  * 一键修改模型名（与 Prompt 一起保存）
  * 版本回滚（选择旧版本恢复）

### 1.14.2 交互设计

* 非弹窗，而是**表格 + 详情面板**：

  * 左侧列表：Agent/Prompt 列表
  * 右侧面板：YAML/表单编辑器
* 编辑器支持 YAML 直改或表单改（切换 Tab）
* 支持“校验”按钮，调用 `POST /api/v1/prompts/validate` 返回渲染结果。

---

## 1.15. API 合同

* `GET /api/v1/prompts`：列出所有 Prompt
* `GET /api/v1/prompts/{id}`：获取 Prompt 详情
* `PUT /api/v1/prompts/{id}`：更新 Prompt，生成新版本
* `POST /api/v1/prompts/validate`：校验变量渲染
* `GET /api/v1/prompts/{id}/history`：返回版本历史（YAML commit 或 DB 记录）

---

## 1.16. 用户体验目标

* 用户在前端可 **同时修改 Prompt 与模型名**，避免两地修改。
* 提供版本回滚，避免误改造成系统异常。
* 不使用弹窗式逐条修改，而是**集中工作台式编辑体验**。

---

## 1.17. 开发任务清单

* [ ] 新建 `domain/prompts/` 与 YAML 文件
* [ ] 实现 PromptRegistry（加载、缓存、更新）
* [ ] 改造 `llm_call` 支持 PromptConfig
* [ ] API：`GET/PUT prompts`、`POST validate`、`GET history`
* [ ] 前端 PromptStudio 页面（表格+详情面板）
* [ ] 支持 Prompt 与模型参数一并编辑保存

---

## 2. 多工作流支持（Workflow Registry + 选择器）

### 2.1 目录与发现机制

```
backend/src/app/domain/workflows/
├── registry.py                 # 统一注册：枚举/动态发现工作流
├── textbook/                   # 既有工作流（保留）
│   └── graph.py                # get_workflow() 暴露入口
└── quiz_maker/                 # 示例：新工作流（可选）
    └── graph.py                # get_workflow()
```

* **约定**：每个工作流子包必须导出：

  * `get_workflow() -> Graph`
  * `get_metadata() -> {id, name, description, input_schema, ui_schema}`

### 2.2 API 合同

* `GET /api/v1/workflows`：枚举可用工作流（含输入 Schema，用于动态表单）
* `POST /api/v1/runs` 新增参数：`workflow_id`（默认 `textbook` 以兼容旧前端）

### 2.3 前端改造

* 首页增加 **工作流选择卡片**：

  * 路由：`/workflows`（或首页即展示）
  * 选择后根据 `input_schema` 动态渲染表单（如：章节数/语言等）

---

## 3. RAG 集成（知识库 / 检索管线 / 节点注入）

> 决策落地：**混合检索** 采用「**双通道并行检索 + 合并重排**」；向量库选 **Qdrant**，图谱库沿用 **Neo4j**。  
> 流程：**Qdrant 向量检索**（语义召回） + **Neo4j KG 检索**（结构关系） → **Merger/Rerank** → Prompt 构造 → LLM。

### 3.1 放置目录（代码 & 数据）

```bash
# 代码
backend/src/app/infrastructure/rag/
├── chunker.py                 # 文档分块（Markdown/HTML/PDF/TXT）
├── embedder.py                # 向量化（默认：BAAI/bge-small-zh-v1.5）
├── vectorstores/
│   └── qdrant_store.py        # Qdrant 读写封装（集合管理/批量upsert）
├── kgstores/
│   └── neo4j_queries.py       # Neo4j 检索（实体/路径/子图）与写入辅助
├── retrievers/
│   ├── retriever_vector.py    # 向量检索 Top-k（Qdrant）
│   └── retriever_kg.py        # KG 检索（Cypher），可限制跳数/关系类型/时间
├── rerankers/
│   └── bge_reranker.py        # 交叉编码器复排（可关）
├── merger.py                  # 双通道结果合并+打分归一+去重
├── prompt_builder.py          # 将证据片段+子图转为可读上下文
└── pipeline.py                # 统一对外：ingest / index / retrieve / test

# 数据（持久层）
knowledge_base/
├── raw/                       # 原始上传文档（原样存档）
├── chunks/                    # 分块后 JSONL（含meta/embedding_id等）
└── snapshots/                 # 可选：索引/集合快照与统计（不存向量本体）

# 容器卷（由 docker-compose 管理）
# - qdrant_data:/qdrant/storage               # Qdrant 索引/向量
# - neo4j_data:/data                          # Neo4j 图数据
# - <backend_volume>:/app/knowledge_base      # 文本及中间件
````

> 与原设计差异：移除 `index_faiss.py` 与 `index/FAISS` 文件夹；向量索引改由 **Qdrant** 统一管理（持久化在其容器卷）。

---

### 3.2 环境与 Docker 编排

**后端 .env（新增 Qdrant 配置）**

```dotenv
# Qdrant
APP_QDRANT__URL=http://qdrant:6333
APP_QDRANT__API_KEY=                # 本地无需；云端自配
APP_QDRANT__COLLECTION=kb_chunks
APP_QDRANT__DISTANCE=cosine         # 余弦/点积/欧氏，默认 cosine
APP_QDRANT__HNSW_M=16               # HNSW 参数（可调）
APP_QDRANT__HNSW_EF_CONSTRUCTION=128
APP_QDRANT__OPTIMIZER_MEM_LIMIT_MB=2048

# Neo4j（已存在）
APP_NEO4J__URI=bolt://neo4j:7687
APP_NEO4J__USER=neo4j
APP_NEO4J__PASSWORD=your_password
APP_NEO4J__DATABASE=neo4j
```

**docker-compose（新增 Qdrant 服务，建议单独 overlay）**

```yaml
# docker-compose.vectordb.yml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: sopilot-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  qdrant_data:
```

运行方式（叠加）：

```bash
docker compose -f docker-compose.yml -f docker-compose.vectordb.yml up -d --build
```

> 体积提示：新增 Qdrant 镜像 \~150–350 MB（压缩拉取体积），可接受。Milvus 体积更大（多容器，2.5–3.5 GB），本项目首选 **Qdrant 轻量**方案。

---

### 3.3 API 合同（知识库管理 & 调试）

* `GET    /api/v1/rag/docs`：列出文档（文件名/大小/更新时间/索引状态）
* `POST   /api/v1/rag/docs`：上传文档（多文件）
* `DELETE /api/v1/rag/docs/{name}`：删除文档（同时删除向量与元数据）
* `POST   /api/v1/rag/reindex`：重建索引（全量/增量；可选 `{"clean":true}`）
* `POST   /api/v1/rag/test_vector`：`{query, top_k}` → 返回向量通道命中
* `POST   /api/v1/rag/test_kg`：`{query, hop, rel_types[]}` → 返回 KG 子图/证据
* `POST   /api/v1/rag/test_dual`：`{query}` → 返回合并/复排后的最终证据包

**标准响应（test\_dual）**

```json
{
  "query": "什么是注意力机制？",
  "vector_hits": [
    {"doc":"...", "chunk":"...", "score":0.81, "meta":{"section":"...", "page":1}}
  ],
  "kg_hits": [
    {"path":"Concept(注意力)->DEFINES->Method(Scaled Dot-Product)", "score":0.66}
  ],
  "merged": [
    {"type":"chunk","id":"...","score":0.73},
    {"type":"kg_path","id":"...","score":0.62}
  ],
  "prompt_preview": "…（截断）…"
}
```

---

### 3.4 数据建模（RAG 视角的最小约定）

* `(:Doc)-[:HAS_CHUNK]->(:Chunk {id, text, tokens, lang, ...})`
* `(:Entity {name, aliases, ...})`
* `(:Chunk)-[:MENTIONS]->(:Entity)` **（连接检索与图谱的关键边）**
* 向量仅存于 Qdrant；Chunk 节点保存 `embedding_id`/`vector_id` 以便反查。

---

### 3.5 索引与入库（ingest → index）

1. **文本分块** `chunker.py`

   * 默认参数：`chunk_size=800, chunk_overlap=120`（中文/中英混排友好）
   * 输出：`chunks/*.jsonl`，每行包含 `chunk_id/doc_id/text/meta`

2. **向量化** `embedder.py`

   * 默认 `BAAI/bge-small-zh-v1.5`（中/英都可用）
   * 支持批处理+GPU；可替换为自选模型（接口统一）

3. **写入 Qdrant** `vectorstores/qdrant_store.py`

   * 集合 schema：`vector: float[dim] + payload(meta)`
   * 元数据字段（最少）：`doc_id, chunk_id, section, lang, created_at`

4. **关联 KG** `kgstores/neo4j_queries.py`

   * 可选：抽取实体后建立 `(:Chunk)-[:MENTIONS]->(:Entity)`，为 KG 检索补证据。

---

### 3.6 在工作流中的注入点（LangGraph）

* **researcher 节点**

  * 将 `{topic/subchapter}` → `query`
  * 并行调用：

    * `retriever_vector.search(query, top_k=k1, filters=...)`
    * `retriever_kg.subgraph(query, hop=h, rel_types=..., limit=k2)`
  * 输出 `research_content` 附带 `evidence.vector / evidence.kg`

* **writer 节点**

  * 通过 `prompt_builder` 注入“引用材料”（标明来源：文档/页码/实体路径）

* **validator 节点（可选）**

  * 反向检索核验关键断言（期望能命中至少 N 条可靠证据），生成“证据充分度”。

---

### 3.7 打分、合并与复排（核心）

**召回规模（默认）**

* 向量通道：`k1 = 12`
* KG 通道：`k2 = 8`
* 合并后复排取：`k_final = 4`

**归一化与融合**

```text
vector_score' = minmax(vector_score)
kg_score'     = path_score(path_len, edge_conf, support_count)  # 见下
final_score   = α * vector_score' + β * kg_score'
默认 α=0.7, β=0.3
```

**KG 路径打分（建议）**

* `path_len`: 越短越好（建议 `1/len`）
* `edge_conf`: 关系字段 `confidence` 的均值/最小值
* `support_count`: 该路径涉及的 `MENTIONS` 支持次数
  **示例**：`kg_score = 0.6*(1/len) + 0.3*avg_conf + 0.1*log(1+support)`

**复排（可关）**

* `rerankers/bge_reranker.py` 使用 `bge-reranker-base` 交叉编码器
* 复排对象：合并后的候选（文本片段与 KG 解释串）
* 产出：最终 Top-`k_final` 证据列表（携带来源与可视化 info）

---

### 3.8 前端（Knowledge Base & RAG 调试面板）

* **KnowledgeBase.vue**：文件上传/删除、索引状态、样例检索预览
* **新增 RAG 设置项**（运行创建页）：

  * 复选：「启用 RAG」
  * 数值：`top_k`、`k1/k2/k_final`、`α/β`、`hop`、`rel_types[]`
  * 开关：「启用复排」
* **调试页**（可复用现有日志页侧栏）：输入 `query` → 展示

  * **向量命中**、**KG 命中**、**合并与复排**、**Prompt 预览**

---

### 3.9 参数与默认值（MVP）

* 分块：`chunk_size=800`，`chunk_overlap=120`
* 向量检索：`k1=12`，距离 `cosine`
* KG 检索：`k2=8`，默认 `hop=2`，关系类型白名单可为空
* 合并权重：`α=0.7`，`β=0.3`
* 复排：默认 **开启**，模型 `bge-reranker-base`；`k_final=4`
* 嵌入：`BAAI/bge-small-zh-v1.5`

---

### 3.10 关键代码片段（示例伪代码）

```python
# pipeline.py
def dual_retrieve(query: str, top_k_final=4):
    vec_hits = retriever_vector.search(query, top_k=12)        # Qdrant
    kg_hits  = retriever_kg.subgraph(query, hop=2, limit=8)    # Neo4j

    merged   = merger.combine(vec_hits, kg_hits, alpha=0.7, beta=0.3)
    reranked = bge_reranker.rerank(query, merged)              # 可开关

    prompt   = prompt_builder.build(query, reranked[:top_k_final])
    return {"vector_hits": vec_hits, "kg_hits": kg_hits,
            "merged": reranked[:top_k_final], "prompt": prompt}
```

---

### 3.11 权限与过滤（可选）

* Payload 过滤：为每个 Chunk 增加 `tenant_id / project_id / visibility`
* 查询时传入过滤器，Qdrant 支持 `must/should/must_not` 过滤组合；KG 查询加 `WHERE n.scope = $scope`

---

### 3.12 监控与评估（建议）

* 指标：**召回/复排命中率**、**首位命中率@1**、**证据充分度均值**、**平均响应时延**
* 采样集：维护 `eval/queries.jsonl`，包含标准答案/引用，定期离线评测
* 日志：为每次检索记录 `query/hash`、参数、候选与最终证据、用时

---
# 真·Neo4j 教材 → 知识图谱（工程化分层解耦实施手册）

> 本手册是 **SOPilot** 项目中“教材 → 知识图谱”部分的**唯一实施标准**。 目标：让**新接手的开发者**在 1 天内完成一次端到端小节级 KG 构建，并在 2 天内完成整书级合并与前端可视化接入。
>
> **禁止自由发挥**：所有模块路径、函数命名、输入输出模式、配置键名、默认阈值、索引约束、API 合同均已在本文中固定，不得擅自更改。

---

## 0. 成果定义（Definition of Done）

一次成功的“教材 → 知识图谱”流水线运行，必须满足：

1. **小节级图谱（Section Scope）** 已存入 Neo4j：

   * 至少 10 个 `Concept` 节点、20 条 `REQUIRES/EXPLAINS/PART_OF/MENTIONS` 关系；
   * 每条关系带 `src=<section_id>`、`scope=<section_id>`、`rid` 唯一键；
   * 每个被关系引用的节点均唯一（`id` 唯一约束生效）。
2. **整书级图谱（Book Scope）** 已合并：

   * `scope=book:{topic}:{8位短哈希}`；
   * 合并时按 `rid` 去重，按 `scope` 替换更新（删除旧书、写入新书）。
3. **RAG 联动**：每个 `Concept` 至少被一个 `Chunk` 以 `MENTIONS` 连接（证据可回链）。
4. **前端渲染**：`/runs/:id` 的 KG 标签页可成功拉取 **Book Scope** 并渲染。
5. **自动化校验**：执行 `pytest -k test_kg_pipeline` 全部通过；运行 `scripts/kg_smoke.ps1` 返回 `OK`。

---

## 1. 目录与文件落位（固定，不得变更）

```
backend/src/app/domain/kg/
├── pipeline.py         # KGPipeline：端到端编排（唯一入口）
├── builder.py          # NER/RE 抽取（句级/段级，不得整篇丢 LLM）
├── normalizer.py       # 规范化（大小写、词形、别名映射、停用词）
├── linker.py           # 实体链接（对齐已有节点；规则+向量）
├── idempotent.py       # ID 与 RID 生成、查重
├── store.py            # 写 Neo4j（节点/关系 MERGE；批量事务）
├── merger.py           # 整书合并（Section → Book 合并与去重）
└── service.py          # 查询与服务层（供 API 调用）

backend/src/app/infrastructure/graph_store/
├── neomodel_conn.py      # neomodel 连接初始化
├── schema.py             # 约束/索引安装
└── neomodel_store.py     # 统一 Neo4j 会话与执行器（neomodel）

backend/src/app/api/v1/kg.py           # KG API（新增/完善端点）
backend/src/app/core/settings.py       # 配置入口（增加 KG_* 配置）
backend/tests/test_kg_pipeline.py      # 端到端与单元测试
scripts/kg_smoke.ps1                   # 一键冒烟
```

> **说明**：如需新增工具文件，只能放入 `backend/src/app/domain/kg/_utils/`，且需在本文新增“白名单”清单。

---

## 2. 运行前置与依赖（固定版本）

### 2.1 Python 依赖（追加到 `requirements.txt`）

```
# 本模块新增（固定安装）
neomodel==5.0.1
spacy==3.7.4
rapidfuzz==3.9.6
numpy==1.26.4
```

> 说明：
>
> 1. **neomodel 5.x 版本变化**：从 5.0 开始，`db.set_connection()` 不再更新 `config.DATABASE_URL`，必须直接设置 `config.DATABASE_URL`。项目使用 5.0.1。
> 2. **仅安装 spaCy**（用于分词/句切分/NER/依存句法），**不安装 transformers / sentence-transformers / scispacy**。
> 3. 本项目已全局依赖 `httpx`，无需在本模块重复声明；RE 与 Embedding **全部通过 API** 调用完成（见 2.2）。

> **禁止** 在 builder 中对**整篇文档**进行 LLM 抽取。允许在 **句级/段级（按 chunk）** 通过项目内 `llm_service` 调用通用 LLM 执行 **关系抽取（RE）** 的**结构化 JSON** 输出；**NER 不使用 LLM**，由 spaCy 完成。

### 2.2 外部 API 资源（RE / Embedding）

* **关系抽取（RE）**：调用 `llm_service` 统一路由的通用 LLM（默认 **SiliconFlow** 提供商），模型示例：`Qwen/Qwen2.5-7B-Instruct` 或等价兼容模型。**不下载本地 RE 模型**。
* **Embedding（实体链接）**：调用 `llm_service` 的 Embedding 接口（默认 **SiliconFlow** + `BAAI/bge-m3` 或等价多语模型）。**不安装 sentence-transformers**。

> 运行策略：严格按 **句级/段级** 发送最小上下文（<= 800 汉字）；超限截断；返回 **受控 JSON**（见 5.2.1）。

---

## 3. 配置（`settings.py` 固定键名）

在 `Settings` 中新增以下字段（下划线分隔、可被环境变量覆盖）：

```python
class Settings(BaseSettings):
    # —— KG 主开关 ——
    KG_ENABLED: bool = True

    # —— 语言（仅 'zh' 或 'en'；本手册以中文为既定）——
    KG_LANGUAGE: Literal['zh', 'en'] = 'zh'

    # —— 抽取阈值（固定，不提供开关）——
    KG_MIN_TERM_LEN: int = 2            # 概念最小字符数
    KG_RE_MIN_CONF: float = 0.55        # RE 最小置信度（LLM 输出中的 confidence 字段低于此阈值丢弃）

    # —— 链接相似度（Embedding 相似度阈值）——
    KG_LINK_MIN_SIM: float = 0.82
    KG_LINK_TOPK: int = 3

    # —— 并发与批量 ——
    KG_MAX_WORKERS: int = 50
    KG_TX_BATCH_SIZE: int = 256

    # —— 提供商（固定走 llm_service，不落地模型）——
    KG_RE_PROVIDER: str = 'llm'                 # 关系抽取统一使用通用 LLM
    KG_RE_MODEL: str = 'Qwen/Qwen2.5-7B-Instruct'
    KG_EMBEDDING_MODEL: str = 'BAAI/bge-m3'     # 实体链接使用的向量模型（API 侧实现）

    # —— Neo4j / neomodel 连接 ——
    NEO4J_BOLT_URL: str = 'bolt://neo4j:neo4j@localhost:7687'  # 形如 bolt://user:pass@host:7687
    NEO4J_MAX_CONNECTION_LIFETIME: int = 3600
```

**环境变量示例（**\`\`**）**

```
APP_KG__ENABLED=true
APP_KG__LANGUAGE=zh
APP_KG__RE_MIN_CONF=0.55
APP_KG__LINK_MIN_SIM=0.82
APP_KG__TX_BATCH_SIZE=256
```

### 3.1 启动顺序（必须执行）

1. 在应用启动时调用 `init_neo4j(settings)`（文件：`backend/src/app/infrastructure/graph_store/neomodel_conn.py`）。
2. 紧接着执行 `install_schema()`（文件：`backend/src/app/infrastructure/graph_store/schema.py`）。
3. 然后启动 FastAPI 应用。

### 3.2 连接初始化（`neomodel_conn.py`）

```python
from neomodel import config

__all__ = ["init_neo4j"]

def init_neo4j(settings) -> None:
    """设置 neomodel 连接（应用启动时调用一次）。
    
    注意：neomodel 5.x 必须直接设置 config.DATABASE_URL，
    使用 db.set_connection() 不会更新底层配置。
    """
    config.DATABASE_URL = settings.NEO4J_BOLT_URL
    # 连接参数按需可在 URL 中指定；不在代码里二次覆盖。
```

---

## 4. 数据模型（节点/关系/索引：固定）

### 4.1 节点标签（仅允许以下）

`Concept`, `Chapter`, `Subchapter`, `Method`, `Example`, `Dataset`, `Equation`, `Doc`, `Chunk`

### 4.2 关系类型（仅允许以下）

* 结构：`PART_OF`（Subchapter→Chapter）、`HAS_SECTION`（Chapter→Subchapter）、`HAS_CHUNK`（Doc→Chunk）
* 语义：`DEFINES`, `EXPLAINS`, `REQUIRES`, `SIMILAR_TO`, `CONTRASTS_WITH`, `IMPLEMENTS`
* 桥接：`MENTIONS`（Chunk→Entity）

### 4.3 节点属性（最小集合）

`id, name, type, desc, aliases[], scope, created_at, updated_at`

### 4.4 关系属性（最小集合）

`rid, type, src(section_id), scope(book_id or section_id), confidence, weight, created_at, evidence`

### 4.5 架构安装（通过 `schema.py` 一次性执行）

文件：`backend/src/app/infrastructure/graph_store/schema.py`

```python
from neomodel import db
from app.domain.kg.models import (
    Concept, Chunk, BaseEntity
)

__all__ = ["install_schema"]

NODE_CONSTRAINTS = [
    "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (n:Concept) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id   IF NOT EXISTS FOR (n:Chunk)   REQUIRE n.id IS UNIQUE",
    "CREATE INDEX     node_scope  IF NOT EXISTS FOR (n) ON (n.scope)",
]

REL_INDEXES = [
    "CREATE INDEX rel_scope IF NOT EXISTS FOR ()-[r]-() ON (r.scope)",
    "CREATE INDEX rel_rid   IF NOT EXISTS FOR ()-[r]-() ON (r.rid)",
]

def install_schema() -> None:
    """一次性执行，重复调用安全。"""
    # 节点约束/索引（也可通过 neomodel 的 labels 安装，但此处统一显式执行）
    for cypher in NODE_CONSTRAINTS + REL_INDEXES:
        db.cypher_query(cypher)
```

> 执行位置：应用启动顺序中 `init_neo4j(settings)` 之后调用 `install_schema()`；`scripts/kg_smoke.ps1` 亦应调用。

### 4.6 neomodel 模型定义（固定）

文件：`backend/src/app/domain/kg/models.py`

```python
from datetime import datetime
from neomodel import (
    StructuredNode, StructuredRel,
    StringProperty, FloatProperty, DateTimeProperty, ArrayProperty,
)

# —— 关系属性：固定最小集合；可选 evidence 便于溯源 ——
class KGRel(StructuredRel):
    rid       = StringProperty(required=True)        # 关系唯一键（由 pipeline 计算）
    type      = StringProperty(required=True)        # 关系类型（与边类型一致）
    src       = StringProperty(required=True)        # 小节级来源 section_id
    scope     = StringProperty(required=True)        # section_id 或 book_id
    confidence= FloatProperty(default=1.0)
    weight    = FloatProperty(default=1.0)
    created_at= DateTimeProperty(default_now=True)
    evidence  = StringProperty()                     # 选填：对齐的 chunk_id

# —— 节点公共基类 ——
class BaseEntity(StructuredNode):
    id         = StringProperty(required=True, unique_index=True)  # 全局唯一
    name       = StringProperty(required=True)
    type       = StringProperty(required=True)                     # 固定为标签名
    desc       = StringProperty()                                  # ≤ 2KB，外部保证截断
    aliases    = ArrayProperty()
    scope      = StringProperty()                                  # 可留空；用于 Doc/Chunk
    created_at = DateTimeProperty(default_now=True)
    updated_at = DateTimeProperty(default_now=True)

    def touch(self):
        self.updated_at = datetime.utcnow()
        self.save()

# —— 9 类节点（标签名 = 类名）——
class Concept(BaseEntity):
    pass

class Chapter(BaseEntity):
    pass

class Subchapter(BaseEntity):
    pass

class Method(BaseEntity):
    pass

class Example(BaseEntity):
    pass

class Dataset(BaseEntity):
    pass

class Equation(BaseEntity):
    pass

class Doc(BaseEntity):
    pass

class Chunk(BaseEntity):
    pass
```

---

## 5. 流水线（端到端强约束）

### 5.1 统一入口（禁止旁路）

#### 5.1.1 Section 级流水线

`KGPipeline.run(section: SectionInput) -> KGPipelineResult`

每个 **subchapter（小节）** 独立调用 `pipeline.run()`，只负责 Section Scope 的图谱构建：

```python
# backend/src/app/domain/kg/pipeline.py
from .builder import KGBuilder
from .normalizer import KGNormalizer
from .linker import EntityLinker
from .idempotent import IdGen
from .store import KGStore

class KGPipeline:
    def __init__(self, settings):
        self.builder = KGBuilder(settings)
        self.normalizer = KGNormalizer(settings)
        self.linker = EntityLinker(settings)
        self.idgen = IdGen(settings)
        self.store = KGStore(settings)
        # 注意：不在这里初始化 BookMerger

    def run(self, section: dict) -> dict:
        """section = {
            'section_id': 'sec_xxx',
            'book_topic': '大型语言模型',
            'chapter_title': 'RAG 基础',
            'subchapter_title': '向量检索',
            'chunks': [
                {'id': 'doc1#p3', 'text': '...'},
                ...
            ]
        }"""
        # 1) 抽取（NER/RE）
        draft = self.builder.extract(section)
        # 2) 规范化
        draft = self.normalizer.normalize(draft)
        # 3) 实体链接（对齐既有图谱）
        linked = self.linker.link(draft)
        # 4) 生成 ID/RID
        ready = self.idgen.assign(linked, section)
        # 5) 小节级入库（Section Scope）
        self.store.write_section(ready, section['section_id'])
        
        # ⚠️ 注意：不在这里调用 merge_book()
        # Book Scope 合并由外层工作流统一调度（见 5.1.2）
        return {
            'section_id': section['section_id'], 
            'book_id': None,  # 由外层统一生成
            'stats': self.store.stats
        }
```

#### 5.1.2 Book 级合并（工作流层）

整书合并**不在** `pipeline.run()` 中执行，而由外层工作流在 **所有 section 完成后** 统一调度：

```python
# backend/src/app/domain/workflows/textbook/nodes/book_graph_node.py
from app.domain.kg import BookMerger, generate_book_id

def book_graph_node(state: dict) -> dict:
    """
    整本书图谱持久化节点（在所有 section 处理完成后执行）
    
    职责：
    1. 生成 book_id
    2. 从 Neo4j 读取所有 section 数据
    3. 调用 BookMerger.merge_book() 汇总为 Book Scope
    """
    topic = state.get("topic")
    language = state.get("language", "zh")
    
    # 1) 生成 book_id（只执行一次）
    book_id = generate_book_id(topic, language)
    
    # 2) 整书合并（删除旧 book 关系 + 汇总 section 关系）
    merger = BookMerger(settings)
    merger.merge_book(topic)
    
    return {
        "book_id": book_id,
        "book_store_stats": {...}
    }
```

**工作流边连接**：

```python
# backend/src/app/domain/workflows/textbook/graph.py
workflow.add_edge("kg_builder", "book_graph")   # 所有 section 完成后
workflow.add_edge("book_graph", "merger")       # 整书合并完成后
```

**核心原则**：
- ✅ **Section Scope**：`pipeline.run()` 只写 section 级关系（`scope=section_id`）
- ✅ **Book Scope**：`book_graph_node` 统一转写为书籍级关系（`scope=book_id`）
- ✅ **单次合并**：`merge_book()` 只在所有 section 完成后调用 **1 次**
- ❌ **禁止重复**：每个 section 都调用 `merge_book()` 会导致 N-1 次无效删除+重建

### 5.2 抽取（`builder.py`）

* **粒度**：以 **Chunk（段落）** 为单位；内部再做**句切分**。
* **NER**：使用 **spaCy** 抽取候选概念（最小长度、停用词过滤）。
* **RE**：对每个**句子**调用 `llm_service` → 通用 LLM（默认 SiliconFlow）输出**受控 JSON** 的 `(head, relation, tail, confidence, evidence)` 三元组。**禁止**整篇/整段直接让 LLM“自由发挥”。
* **去噪**：丢弃 `confidence < KG_RE_MIN_CONF`；head/tail 必须能在 NER 或文本片段中对齐；relation 必须能规约到**枚举**（见 8.4）。

```python
class KGBuilder:
    def __init__(self, settings):
        self.nlp = load_spacy('zh_core_web_sm')  # 仅 spaCy，本地
        self.min_len = settings.KG_MIN_TERM_LEN
        self.conf_threshold = settings.KG_RE_MIN_CONF

    def extract(self, section: dict) -> dict:
        concepts, relations = [], []
        for ch in section['chunks']:
            doc = self.nlp(ch['text'])
            # 1) NER：收集候选概念
            ents = [e.text for e in doc.ents if len(e.text) >= self.min_len]
            concepts.extend({'name': t, 'mentions': [ch['id']]} for t in set(ents))
            # 2) RE：句级调用 llm_service（受控 JSON）
            for sent in doc.sents:
                payload = {
                    'task': 're',
                    'text': sent.text,
                    'language': 'zh',
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'relations': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'head': {'type': 'string'},
                                        'relation': {'type': 'string'},
                                        'tail': {'type': 'string'},
                                        'confidence': {'type': 'number'}
                                    },
                                    'required': ['head','relation','tail']
                                }
                            }
                        },
                        'required': ['relations']
                    }
                }
                res = llm_service.call_structured(payload)  # 统一路由
                for r in res.get('relations', []):
                    rel = normalize_relation(r['relation'])  # 映射到枚举
                    if rel and r.get('confidence', 1.0) >= self.conf_threshold:
                        relations.append({
                            'src_name': r['head'],
                            'tgt_name': r['tail'],
                            'type': rel,
                            'confidence': r.get('confidence', 1.0),
                            'evidence': ch['id']
                        })
        return {'concepts': dedup(concepts), 'relations': dedup(relations)}
```

#### 5.2.1 RE API（受控 JSON）合同

* **调用入口**：内部统一走 `llm_service`；Provider 默认 **SiliconFlow**；温度固定 `0.1`；不允许流式。
* **输入**：单句文本（来自 chunk 的句切分），可附上候选实体清单 `candidates=[...]` 以降低幻觉。
* **输出**：

```json
{"relations":[{"head":"RAG","relation":"REQUIRES","tail":"向量检索","confidence":0.91}]}
```

* **后处理**：

  * `relation` 必须映射到枚举：`DEFINES|EXPLAINS|REQUIRES|SIMILAR_TO|CONTRASTS_WITH|IMPLEMENTS|PART_OF`；否则丢弃。
  * `head/tail` 必须能在句内出现或与 NER 候选对齐；否则丢弃。
  * 每条关系绑定 `evidence=chunk_id`。

### 5.3 规范化（`normalizer.py`）

* 小写化、全半角、去噪；
* 同义/别名映射（静态词典 + 规则）；
* 术语词形归一（英文词形还原）。

```python
class KGNormalizer:
    def normalize(self, draft: dict) -> dict:
        # 归一 name/aliases；去重；剔除过短项
        return draft
```

### 5.4 实体链接（`linker.py`）

* **先规则**：名称规范化后做**完全/别名匹配**；
* **再语义**：通过 **Embedding API**（SiliconFlow + `BAAI/bge-m3`）计算相似度；`cosine ≥ KG_LINK_MIN_SIM` 复用已有节点，否则新建；
* **不安装本地 sentence-transformers**；不做本地向量推理。

```python
class EntityLinker:
    def __init__(self, settings):
        self.threshold = settings.KG_LINK_MIN_SIM
        self.knn = preload_concept_vectors()  # 从 Neo4j/Qdrant 预取 name/alias 向量

    def link(self, draft: dict) -> dict:
        out = []
        for c in draft['concepts']:
            # 规则匹配
            found = exact_or_alias_match(c['name'])
            if found:
                c['existing_id'] = found['id']
                out.append(c)
                continue
            # 语义匹配（API）
            v = embedding_api.embed(c['name'])
            hits = self.knn.search(v, top_k=3)
            if hits and hits[0].score >= self.threshold:
                c['existing_id'] = hits[0].id
            out.append(c)
        draft['concepts'] = out
        return draft
```

### 5.5 幂等与 ID（`idempotent.py`）

* 节点 `id = concept:{slug(name)}:{md5(topic|chapter|subchapter)[:6]}`；
* 关系 `rid = md5(type|source_id|target_id|scope)[:16]`。

```python
class IdGen:
    def assign(self, linked: dict, section: dict) -> dict:
        # 对 new 概念生成 id；对每条关系生成 rid；补齐 src/scope/evidence
        return ready
```

### 5.6 入库（`store.py`）

* 通过 neomodel 的 `db` 执行；
* **必须** 批量事务（`KG_TX_BATCH_SIZE`）；
* 删除旧 Section 边 → MERGE 节点 → MERGE 关系（以 `rid` 幂等）；
* 失败回滚并抛出。

```python
from typing import Iterable
from itertools import islice
from neomodel import db
from .models import Concept, Chunk
from app.infrastructure.graph_store.neomodel_store import Neo4jStore

class KGStore:
    """使用 neomodel 完成小节级写入（先删旧边 → 节点 MERGE → 关系 MERGE）。"""

    def __init__(self, settings):
        self.batch = settings.KG_TX_BATCH_SIZE
        self.stats = {"nodes": 0, "edges": 0}

    def write_section(self, ready: dict, section_id: str) -> None:
        self._delete_section_edges(section_id)
        self._merge_concepts_batched(ready.get('concepts', []))
        self._merge_evidence_chunks(ready.get('concepts', []))
        self._merge_relations_batched(ready.get('relations', []))

    def _delete_section_edges(self, section_id: str) -> None:
        Neo4jStore.run_cypher("MATCH ()-[r]-() WHERE r.scope = $scope DELETE r", {"scope": section_id})

    def _merge_concepts_batched(self, concepts: list[dict]) -> None:
        for chunk in _chunked(concepts, self.batch):
            with db.transaction:
                for c in chunk:
                    node = Concept.nodes.get_or_none(id=c['id'])
                    if node is None:
                        Concept(id=c['id'], name=c['name'], type='Concept', aliases=c.get('aliases', [])).save()
                        self.stats["nodes"] += 1
                    else:
                        if c.get('name') and node.name != c['name']:
                            node.name = c['name']
                        if c.get('aliases'):
                            node.aliases = sorted(set((node.aliases or []) + c['aliases']))
                        node.touch()

    def _merge_evidence_chunks(self, concepts: list[dict]) -> None:
        all_mentions = []
        for c in concepts:
            all_mentions.extend(c.get('mentions', []))
        ids = sorted(set(all_mentions))
        for chunk in _chunked(ids, self.batch):
            with db.transaction:
                for cid in chunk:
                    if not cid:
                        continue
                    node = Chunk.nodes.get_or_none(id=cid)
                    if node is None:
                        Chunk(id=cid, name=cid, type='Chunk').save()
                        self.stats["nodes"] += 1

    def _merge_relations_batched(self, rels: list[dict]) -> None:
        for batch in _chunked(rels, self.batch):
            with db.transaction:
                for r in batch:
                    self._merge_rel(r)
                    self.stats["edges"] += 1

    @staticmethod
    def _merge_rel(r: dict) -> None:
        cypher = (
            "MATCH (s {id:$sid}), (t {id:$tid}) "
            "MERGE (s)-[e:%s {rid:$rid}]->(t) "
            "SET e.type=$type, e.src=$src, e.scope=$scope, e.confidence=$confidence, "
            "    e.weight=coalesce($weight,1.0), e.created_at=coalesce(e.created_at, datetime()), e.evidence=$evidence"
        ) % r['type']
        params = {
            'sid': r['source_id'], 'tid': r['target_id'], 'rid': r['rid'], 'type': r['type'],
            'src': r['src'], 'scope': r['scope'], 'confidence': float(r.get('confidence', 1.0)),
            'weight': r.get('weight'), 'evidence': r.get('evidence'),
        }
        Neo4jStore.run_cypher(cypher, params)


def _chunked(iterable: Iterable, size: int):
    it = iter(iterable)
    while True:
        batch = list(islice(it, size))
        if not batch:
            return
        yield batch
```

### 5.7 合并（`merger.py`）

**职责**：从 Section Scope 转写为 Book Scope（由 `book_graph_node` 在所有 section 完成后调用）

* ⚠️ **调用时机**：只在 **所有 section 处理完成后** 调用 **1 次**（见 5.1.2）
* 生成 `book_id = book:{slug(topic)}:{md5(topic)[:8]}`；
* 删除旧 `scope=book_id` 的全部关系（幂等清理）；
* 从 Neo4j 读取所有 Section 关系 → 按 `(type, source, target)` 聚合 → 写入 Book Scope（语义边）。

```python
from .idempotent import IdGen
from app.infrastructure.graph_store.neomodel_store import Neo4jStore

class BookMerger:
    def __init__(self, settings):
        self.settings = settings
        self.idgen = IdGen(settings)

    def merge_book(self, topic: str) -> str:
        """
        整书合并：Section Scope → Book Scope
        
        ⚠️ 注意：
        - 只应在所有 section 完成后调用 1 次
        - 如果每个 section 都调用，会导致 N-1 次无效删除+重建
        - 由外层工作流（book_graph_node）统一调度
        
        Args:
            topic: 书籍主题
            
        Returns:
            book_id: 书籍唯一标识
        """
        book_id = f"book:{self.idgen.slug(topic)}:{self.idgen.md5(topic)[:8]}"
        
        # 1) 删除旧的整书关系（幂等）
        Neo4jStore.run_cypher(
            "MATCH ()-[r]-() WHERE r.scope = $scope DELETE r", 
            {"scope": book_id}
        )
        
        # 2) 汇总所有 section 关系 → 写入 book scope
        # 从 Neo4j 中读取所有 section 数据，按语义边类型聚合
        cypher = (
            "MATCH (s)-[r]-(t) WHERE r.src IS NOT NULL "
            "WITH DISTINCT type(r) AS typ, s.id AS sid, t.id AS tid "
            "WITH typ, sid, tid, $scope AS scope "
            "WITH typ, sid, tid, scope, toLower(typ) + '|' + sid + '|' + tid + '|' + scope AS sig "
            "WITH typ, sid, tid, scope, right(toHex(apoc.util.md5(sig)),16) AS rid "
            "MATCH (ss {id:sid}), (tt {id:tid}) "
            "MERGE (ss)-[e:%s {rid:rid}]->(tt) "
            "SET e.type=typ, e.src='__book_merge__', e.scope=scope, "
            "    e.confidence=1.0, e.weight=1.0, e.created_at=coalesce(e.created_at, datetime())"
        )
        
        # 只聚合语义边（不含结构边 PART_OF/HAS_SECTION/MENTIONS）
        for typ in ("DEFINES","EXPLAINS","REQUIRES","SIMILAR_TO","CONTRASTS_WITH","IMPLEMENTS"):
            Neo4jStore.run_cypher(cypher % typ, {"scope": book_id})
        
        return book_id
```

**调用架构**（参考 5.1.2）：

```
Section 1 → pipeline.run() → write_section(scope=sec_1)
Section 2 → pipeline.run() → write_section(scope=sec_2)
   ...
Section N → pipeline.run() → write_section(scope=sec_N)
            ↓
     book_graph_node
            ↓
   BookMerger.merge_book() ← 只调用 1 次
            ↓
   汇总所有 section 关系 → write_book(scope=book_id)
```

---

## 6. Neo4j 交互（统一网关）

`backend/src/app/infrastructure/graph_store/neomodel_store.py` 提供以下**固定**方法（若缺失则补齐）：

```python
from typing import Iterable
from neomodel import db

class Neo4jStore:
    """提供最小访问面以供其他层调用；内部全部走 neomodel 的 db。"""

    @staticmethod
    def run_cypher(query: str, params: dict | None = None) -> list[dict]:
        results, meta = db.cypher_query(query, params or {})
        keys = [m["name"] for m in meta]
        out = []
        for row in results:
            obj = {}
            for k, v in zip(keys, row):
                obj[k] = v
            out.append(obj)
        return out

    @staticmethod
    def run_tx(queries: Iterable[tuple[str, dict]]):
        with db.transaction:
            for q, p in queries:
                db.cypher_query(q, p)
```

> 强制要求：任何需要执行 Cypher 的地方必须通过本网关；禁止在项目中实例化 Neo4j 原生 Driver，所有访问通过 neomodel 连接层完成。

---

## 7. API 合同（Contract-First，不得更改路径）

### 7.1 小节构建（触发流水线）

* **POST** `/api/v1/kg/sections:build`
* **Body**（固定 Schema）：

```json
{
  "section_id": "sec_20250912_0001",
  "book_topic": "大型语言模型",
  "chapter_title": "RAG 基础",
  "subchapter_title": "向量检索",
  "chunks": [
    {"id": "doc1#p3", "text": "向量检索是..."},
    {"id": "doc1#p4", "text": "RAG 依赖于..."}
  ]
}
```

* **200 响应**：`{"section_id":"...","book_id":"book:...","stats":{"nodes":N,"edges":M}}`

### 7.2 整书查询（前端优先）

* **GET** `/api/v1/kg/books/{book_id}` → 返回 `{nodes:[...], edges:[...]}`

### 7.3 小节查询（降级使用）

* **GET** `/api/v1/kg/sections/{section_id}`

> **注意**：前端 `KgGraph.vue` 必须优先请求 **Book Scope**，失败再降级 Section。

---

## 8. 前端对接（强约束）

### 8.1 组件：`frontend/src/components/KgGraph.vue`

* **数据源优先级**：`bookId > sectionId`（禁止反转）；
* **布局**：默认 `cose`；提供“重置布局/刷新数据”按钮；
* **节点样式**：

  * `Concept`：圆角矩形；
  * `Chapter/Subchapter`：圆形；
  * 关系按 `type` 颜色区分；
* **点击行为**：控制台打印 `id/name/type`，下一期再接详情面板。

### 8.2 路由：`/runs/:id` 中 KG 页签

* 进入时调用：`GET /api/v1/kg/books/{book_id}`；
* 如果 404/空，则改为：`GET /api/v1/kg/sections/{latest_section_id}`。

---

## 9. 测试与冒烟（必须通过）

### 9.1 单元测试模板：`backend/tests/test_kg_pipeline.py`

```python
from app.domain.kg.pipeline import KGPipeline

FAKE_SEC = {
  'section_id': 'sec_demo',
  'book_topic': '测试主题',
  'chapter_title': 'Ch1',
  'subchapter_title': 'Sc1',
  'chunks': [
    {'id': 'doc1#p1', 'text': '向量检索属于 RAG 的关键组成。'},
    {'id': 'doc1#p2', 'text': 'RAG 依赖于 检索。'}
  ]
}

def test_run(neo4j, settings):
    out = KGPipeline(settings).run(FAKE_SEC)
    assert out['book_id'].startswith('book:')
```

### 9.2 冒烟脚本：`scripts/kg_smoke.ps1`

```
# 1) 提交约束
# 2) 调用 sections:build
# 3) 查询 book 图返回非空
# 打印 OK
```

---

## 10. 运维与性能（默认值，不得擅改）

* `KG_TX_BATCH_SIZE=256`；
* 写入顺序：**删除旧 Section 关系 → MERGE 节点 → MERGE 关系**；
* 超时：单次事务 ≤ 30s；失败重试 2 次（指数退避）。

---

## 11. 安全与合规

* 所有 `LLM` 调用必须通过项目的 `llm_service` 路由；
* 默认关闭 `KG_USE_LLM_FALLBACK`；
* 不得将整段文本内容写入节点属性 `desc` 超过 2KB（超限截断）。

---

## 12. 变更控制

* 对本文任何改动必须提交 PR，标题以 `[KG-SPEC]` 开头，且在合并前完成：

  1. 端到端冒烟；
  2. 前端渲染验证；
  3. 生产约束重复执行验证（无副作用）。

---

## 13. 附录：查询与调试

### 13.1 证据回链（从实体取证据 Chunk）

```cypher
MATCH (e:Concept {name:$name})
OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(e)
WITH e, collect(c.id)[..10] AS chunk_ids
MATCH p = (e)-[r*1..2]-(nbr)
RETURN e, nodes(p) AS nodes, relationships(p) AS rels, chunk_ids
LIMIT 50;
```

### 13.2 由 Chunk 反查实体与邻域

```cypher
MATCH (c:Chunk {id:$chunk_id})-[:MENTIONS]->(e:Concept)
OPTIONAL MATCH p = (e)-[r*1..2]-(nbr)
RETURN e, nodes(p) AS nodes, relationships(p) AS rels
LIMIT 30;
```

---

### 13.3 异常排查清单

* 图为空：确认 `sections:build` 请求体是否包含 `chunks`；
* 节点未复用：检查 `linker` 相似度阈值 `KG_LINK_MIN_SIM` 是否过高；
* 写入很慢：调低 `KG_TX_BATCH_SIZE` 至 128；
* 前端无图：确认优先请求的是 **Book Scope** 接口；

---

## 14. 迁移注意事项（一次性操作）

* 旧实现中若遗留 `rid` 冲突（同源/同目标/同类型但 `scope` 不同），清理逻辑：

  * 书级合并前先 `MATCH ()-[r]-() WHERE r.src <> r.scope AND r.scope STARTS WITH 'book:' REMOVE r.rid`；
  * 再按合并流程重建书级边（`rid` 以书级 scope 重新计算）。
* 若未安装 APOC，请在 `merger.py` 中改为由 `IdGen` 产生 `rid`，并删除 `toHex(apoc.util.md5(...))` 相关语句。

---

## 15. 开发者不得擅改的清单（硬性约束）

* **不得**新增/更名/删除任何 neomodel 模型类与字段；
* **不得**在 neomodel 之外再引入其他 ORM/驱动；
* **不得**修改批量大小、事务边界与 rid 计算方式；
* **不得**将大段文本（>2KB）写入 `desc`；
* **必须**先删旧 Section 边，再写新数据；
* **必须**以 `rid` 作为关系唯一键进行 `MERGE` 幂等写入。

---

### 附：`IdGen.assign` 输出约定（与 5.6 严格配合）

`IdGen.assign` 必须保证：

```json
{
  "concepts": [
    {"id": "concept:xxx", "name": "RAG", "aliases": ["检索增强生成"], "mentions": ["doc1#p3","doc1#p4"]}
  ],
  "relations": [
    {"rid":"0123456789abcdef","type":"REQUIRES","source_id":"concept:rag","target_id":"concept:vecsearch","src":"sec_0001","scope":"sec_0001","confidence":0.93,"evidence":"doc1#p3"}
  ]
}
```

> 上述结构为 `KGStore.write_section` 的唯一输入合同；任何字段缺失或更名均视为违例。
