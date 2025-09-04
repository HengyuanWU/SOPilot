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

## 4. 真·Neo4j 教材 → 知识图谱（工程化分层解耦版）

> 全面采用 **工程化分层设计**：抽取（Builder）→ 规范化（Normalizer）→ 幂等存储（Store）→ 合并（Merger）→ 查询与渲染（Service）。

### 4.1 数据模型

**节点标签**  
`Concept`, `Chapter`, `Subchapter`, `Method`, `Example`, `Dataset`, `Equation`, `Doc`, `Chunk`

**关系类型**  
- **结构**：`PART_OF`（Subchapter→Chapter）、`HAS_SECTION`（Chapter→Subchapter）、`HAS_CHUNK`（Doc→Chunk）  
- **语义**：`DEFINES`, `EXPLAINS`, `REQUIRES`, `SIMILAR_TO`, `CONTRASTS_WITH`, `IMPLEMENTS`  
- **检索桥接**：`MENTIONS`（Chunk→Entity，用于证据回链）

**节点属性**  
`id, name, type, desc, aliases[], scope, created_at, updated_at`

**关系属性**  
`rid, type, src(section_id), scope(book_id), confidence, weight, created_at`


### 4.2 分层流水线（可插拔组件）

```text
kg_pipeline/
├── builder.py     # 节点：LLM 抽取或规则抽取 → JSON Schema
├── normalizer.py  # 节点：normalize 统一化处理（别名/词形/同义/停用词）
├── idempotent.py  # 节点：幂等ID生成与查重 (node_id, rid)
├── store.py       # 节点：写入Neo4j，保证唯一约束
├── merger.py      # 节点：整书级合并，跨节归并/去重
└── service.py     # 节点：查询API服务层，供前端调用
````

**特点**

* **分层解耦**：每个模块单一职责，可替换/扩展
* **面向对象**：每层实现 `BaseComponent` 接口，支持依赖注入
* **可扩展**：可替换 Builder（LLM/规则）、可替换 Normalizer（规则库/Embedding）
* **可插拔**：任何环节可关闭/跳过（Feature Flag）


### 4.3 幂等与一致性

* 节点：`MERGE (n {id})`，由 `slug(canonical_name)` 或短哈希生成
* 关系：`rid = sha256(source|target|type|scope|content_hash)[:16]`
* 写入策略：

  * **节点**：唯一约束保证幂等
  * **关系**：按 `rid` 去重，按 `scope` 替换更新
* 内容更新：基于 `content_hash` 实现增量更新

**Cypher 约束/索引**

```cypher
CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (n:Concept) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT chunk_id   IF NOT EXISTS FOR (n:Chunk)   REQUIRE n.id IS UNIQUE;
CREATE INDEX     node_scope  IF NOT EXISTS FOR (n) ON (n.scope);
CREATE INDEX     rel_scope   IF NOT EXISTS FOR ()-[r]-() ON (r.scope);
CREATE INDEX     rel_rid     IF NOT EXISTS FOR ()-[r]-() ON (r.rid);
```

### 4.4 查询与服务层（统一 Book Scope）

* 所有前端查询均基于 **Book Scope**（不再支持 Section 回退）
* API 服务层提供：

  * **节点详情接口**：返回基本信息 + 来源 Section + 证据 Chunk IDs
  * **关系详情接口**：返回 `confidence`, `weight`, 解释路径（<=2跳）
  * **子图查询接口**：邻居展开 / 解释路径 / 证据回链


### 4.5 KG × RAG 联动查询示例

**A. 实体邻接子图（带证据）**

```cypher
MATCH (e:Concept {name:$name})
OPTIONAL MATCH (c:Chunk)-[:MENTIONS]->(e)
WITH e, collect(c.id)[..10] AS chunk_ids
MATCH p = (e)-[r*1..2]-(nbr)
RETURN e, nodes(p) AS nodes, relationships(p) AS rels, chunk_ids
LIMIT 50;
```

**B. 由 Chunk 反查相关实体**

```cypher
MATCH (c:Chunk {id:$chunk_id})-[:MENTIONS]->(e:Concept)
OPTIONAL MATCH p = (e)-[r*1..2]-(nbr)
RETURN e, nodes(p) AS nodes, relationships(p) AS rels
LIMIT 30;
```


### 4.6 前端渲染与解释

* **证据列表**：显示 Chunk 摘要（Doc/页码/段落）
* **解释路径**：实体间最短路径（<=2跳）
* **关系属性可视化**：`confidence`/`weight` 图形化展示

### 4.7 工程化特征

* **统一视图**：仅保留 Book Scope，不再做 Section 兼容
* **分层解耦**：抽取 → 规范化 → 幂等 → 存储 → 合并 → 查询
* **可插拔**：替换 Builder、替换 Normalizer、替换 Merger 策略无需修改其他层
* **一致性**：幂等 MERGE + `rid` 去重，保证全局唯一
* **可扩展**：未来可在 Service 层挂接向量库/混合检索，无需改动下游

---

## 5. 教材产物稳定落盘（可下载/可追溯）

### 5.1 目录与命名

* 环境变量：`APP_OUTPUT_DIR`（默认 `./output`）
* 结构：

```
output/
  └── <run_id>/
      ├── book.md                 # 合并后的 Markdown
      ├── book.json               # 结构化元数据（章节树、统计）
      ├── qa.json                 # QA 对
      ├── kg_section_ids.json     # 小节 ID 列表
      ├── book_id.txt             # 整书图谱 ID
      └── logs.ndjson             # 运行日志（SSE 同步写入）
```

### 5.2 API 支持

* `GET /api/v1/runs/{run_id}/artifacts`：列出落盘文件
* `GET /api/v1/runs/{run_id}/download?file=book.md`：单文件下载
* `GET /api/v1/runs/{run_id}/archive.zip`：打包下载

### 5.3 前端

* RunDetail 页面新增 **Artifacts/下载** 标签页：文件列表与一键下载

---

## 6. 迁移与实施顺序（两周 MVP）

**Phase 1（D1–D3）**：Prompt Hub（后端 + 前端只读）

1. 新增 `domain/prompts/` 与 YAML 模板；`registry.py` + API
2. Agent 读取路径切换到 PromptRegistry（保留内置默认）
3. 前端新增 /prompts 列表+详情（先只读）

**Phase 2（D4–D7）**：多工作流 + 落盘

1. `workflows/registry.py` + `GET /workflows` + `POST /runs` 支持 `workflow_id`
2. 首页工作流选择器；动态表单渲染
3. `APP_OUTPUT_DIR` 标准化落盘 + 下载接口 + 前端“Artifacts”

**Phase 3（D8–D12）**：RAG MVP + KG 升级

1. `infrastructure/rag/` + 知识库 API + KB 页面
2. `researcher` 注入检索片段；writer 可选引用
3. KG Builder：JSON Schema 校验 + 规范化/幂等/索引

**Phase 4（D13–D14）**：收尾与回归

1. 端到端冒烟 + 大样本测试
2. 文档/脚本完善、回滚预案

---

## 7. 配置与环境变量（新增）

```bash
# Prompt
APP_PROMPT_DIR=backend/src/app/domain/prompts/agents

# RAG
APP_RAG__BASE_DIR=knowledge_base
APP_RAG__EMBED_MODEL=BAAI/bge-small-zh-v1.5
APP_RAG__TOP_K=4
APP_RAG__USE_RERANKER=false

# Output
APP_OUTPUT_DIR=./output
```

---

## 8. 开发任务清单（可勾选）

*

---

## 9. 讨论留白（可根据需要二选一/后续再议）

* **Prompt 存储**：YAML（Git 版本化） vs SQLite（版本表 + 审计）；MVP 先 YAML，再演进到 DB
* **RAG 向量库**：FAISS（轻量离线） vs pgvector/Chroma（在线可共享）；MVP 先 FAISS
* **重排器**：是否接入 bge-reranker（GPU/CPU 性能影响）
* **鉴权与审计**：Prompt 编辑权限、版本回滚审计（Phase 3+）
* **跨章节合并**：概念同义归并策略与人工确认 UI（Phase 3+）

---

## 10. 附：最小代码骨架

\`\`

```python
from importlib import import_module
from pathlib import Path

_CACHE = {}

def list_workflows():
    base = Path(__file__).parent
    items = []
    for p in base.iterdir():
        if p.is_dir() and (p / 'graph.py').exists() and p.name != '__pycache__':
            mod = import_module(f'app.domain.workflows.{p.name}.graph')
            meta = getattr(mod, 'get_metadata', lambda: {'id': p.name, 'name': p.name, 'description': ''})()
            items.append(meta)
    return items

def get_workflow(workflow_id: str):
    if workflow_id in _CACHE:
        return _CACHE[workflow_id]
    mod = import_module(f'app.domain.workflows.{workflow_id}.graph')
    wf = getattr(mod, 'get_workflow')()
    _CACHE[workflow_id] = wf
    return wf
```

\`\`（简化）

```python
from pathlib import Path
import yaml, time
from typing import Dict

class PromptRegistry:
    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.cache: Dict[str, tuple[float, dict]] = {}

    def _load(self, key: str) -> dict:
        path = self.base / f'{key}.yaml'
        mtime = path.stat().st_mtime
        cached = self.cache.get(key)
        if not cached or cached[0] < mtime:
            data = yaml.safe_load(path.read_text(encoding='utf-8'))
            self.cache[key] = (mtime, data)
        return self.cache[key][1]

    def get(self, agent: str, lang: str = 'zh') -> dict:
        return self._load(f'{agent}.{lang}')
```

（其余骨架略，按上文接口与目录落地即可。）

---
