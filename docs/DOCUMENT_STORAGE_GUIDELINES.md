# DOCUMENT\_STORAGE\_GUIDELINES

## PURPOSE

本规范用于指导开发人员在 **SOPilot 项目** 中统一管理用户上传文档、系统生成文档以及知识库相关文件的存储路径。所有开发必须严格遵循本规范，不允许自由发挥或偏离路径定义，以保证工程化一致性、幂等性和可扩展性。

## STORAGE\_ROOT

所有文档与运行产物必须存储在 **后端容器内的统一根目录**：

```
/app/storage
```

该路径通过 `.env` 文件中的环境变量 **APP\_OUTPUT\_DIR** 配置：

```
APP_OUTPUT_DIR=/app/storage
```

所有后端代码必须通过 `settings.output_dir` 获取该路径，不得硬编码具体路径。

## DIRECTORY STRUCTURE

```
backend/storage/
├── uploads/                      # 用户上传文档（原件）
│   └── {user_id}/{yyyymmdd}/{uuid}_{orig_filename}
├── knowledge_base/               # 知识库目录
│   ├── raw/                      # 入库原始文档（只读，不可修改）
│   ├── chunks/                   # 分块数据，与Qdrant集合一一对应
│   ├── snapshots/                # 知识库快照（版本化存档）
│   └── manifests/                # 文档清单与索引元数据
├── runs/                         # 工作流运行产物
│   └── {run_id}/
│       ├── final/                # 最终可交付物（md/pdf/zip）
│       ├── logs/                 # 日志文件
│       ├── kg/                   # 知识图谱导出（可选）
│       └── state.json            # 运行状态快照
├── cache/                        # 可清理缓存（临时PDF解包、图片等）
└── tmp/                          # 临时文件（崩溃恢复/原子写入）
```

## UPLOADS

1. 用户上传文档必须保存至：`uploads/{user_id}/{yyyymmdd}/{uuid}_{orig_filename}`。
2. 文件名必须包含 `uuid` 前缀，避免命名冲突。
3. 上传文档 **只读** 保存，不允许在原件目录中进行改写或覆盖。
4. 入库动作：上传文档若需进入知识库，必须复制到 `knowledge_base/raw/` 并登记清单。

## KNOWLEDGE\_BASE

1. **raw/** 存储经过指纹去重的原始文档，不可修改。
2. **chunks/** 存储分块后的中间文件，必须与 Qdrant 集合 `kb_chunks` 保持一致。
3. **snapshots/** 保存每次索引/重建的快照文件，文件名格式 `{timestamp}_{job_id}.json`。
4. **manifests/** 存储 JSON/Parquet 清单文件，必须包含文档指纹、来源、入库时间等元数据。

## RUNS

1. 每次工作流运行必须在 `runs/{run_id}/` 下建立独立目录。
2. **final/** 保存最终产物（Markdown、PDF、Zip 等）。
3. **logs/** 保存运行日志，必须按时间滚动或分块存储。
4. **kg/** 保存运行时的知识图谱导出（JSON/CSV），权威存储在 Neo4j。
5. **state.json** 保存运行状态快照，必须完整记录执行进度和错误信息。

## CACHE

1. 用于存储临时解析文件、向量化缓存等。
2. 所有缓存均可随时删除，必须设计为无状态。
3. 不允许将用户上传或最终产物写入 cache/。

## TMP

1. 用于写入中的临时文件（如写入前的临时副本）。
2. 程序必须在写入完成后将文件移动至目标目录。
3. tmp/ 内的文件允许系统异常恢复后自动清理。

## NAMING RULES

1. **文件名**：`{uuid}_{slug(orig_name)}{ext}`，其中 slug 必须去除特殊字符，替换为空格或下划线。
2. **目录名**：必须使用 `{user_id}/{yyyymmdd}/` 或 `{run_id}/` 进行分桶。
3. **去重**：必须基于 `content_hash`，相同内容只存一次。
4. **快照文件**：必须包含时间戳和 job\_id，例如 `20250915_abc123.json`。

## DOCKER VOLUMES

必须在 `docker-compose.yml` 中为以下目录配置持久卷：

1. `neo4j:/data`
2. `qdrant:/qdrant/storage`
3. `app_storage:/app/storage`

示例：

```yaml
volumes:
  app_storage:
  neo4j:
  qdrant:

services:
  backend:
    volumes:
      - app_storage:/app/storage
  neo4j:
    volumes:
      - neo4j:/data
  qdrant:
    volumes:
      - qdrant:/qdrant/storage
```

## ENFORCEMENT

1. 开发人员必须严格按照本规范操作，禁止自定义路径。
2. 所有读写路径必须从 `settings.output_dir` 获取。
3. 未经批准，不得在 `uploads/` 和 `knowledge_base/raw/` 中删除或改写文件。
4. CI/CD 流程必须验证目录完整性和权限设置。

## SUMMARY

* **统一根目录**：`/app/storage`
* **用户上传**：`uploads/`
* **知识库**：`knowledge_base/{raw,chunks,snapshots,manifests}`
* **运行产物**：`runs/{run_id}/`
* **缓存与临时**：`cache/`, `tmp/`
* **严格命名与快照机制**
* **持久化卷必须配置**

此文档是强制性规范，所有开发人员必须严格执行。
