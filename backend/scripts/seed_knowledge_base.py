"""幂等初始化「养老知识库」并挂载到默认智能体。

行为（重复执行完全幂等）：
1. 前置校验 embedding 模型可用，缺失立即失败并指明缺什么，不静默跳过；
2. 知识库「养老知识库」（Milvus 实现）不存在则创建，存在则复用；
3. 逐份对比 knowledge_docs 下的 Markdown 文档与库内文件（按文件名）：
   已入库（indexed）跳过，缺的重新上传，解析/入库失败的续跑对应阶段，
   每阶段带超时上限，任何失败立即报错退出；
4. 把目标 KB id 追加进 default-chatbot 的 config_json.context.knowledges，
   已挂载则不动，不覆写智能体已有配置。

在 api 容器内执行：docker compose exec api uv run python scripts/seed_knowledge_base.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
for import_path in (APP_ROOT, APP_ROOT / "package"):
    import_path_str = str(import_path)
    if import_path_str not in sys.path:
        sys.path.insert(0, import_path_str)

KB_NAME = "养老知识库"
KB_DESCRIPTION = "养老领域内置知识库：慢性病管理、权益保障、护理规范、防诈骗指南"
KB_TYPE = "milvus"
EMBEDDING_SPEC_ENV = "YUXI_KB_EMBEDDING_MODEL_SPEC"
DOCS_DIR_ENV = "YUXI_KNOWLEDGE_DOCS_DIR"
OPERATOR_ID = "seed-script"
PARSE_TIMEOUT_SECONDS = 300
INDEX_TIMEOUT_SECONDS = 600

# 与 yuxi.knowledge.base.FileStatus 的取值保持一致；不 import 是为了单测不拉起知识库依赖
STATUS_UPLOADED = "uploaded"
STATUS_PARSING = "parsing"
STATUS_PARSED = "parsed"
STATUS_ERROR_PARSING = "error_parsing"
STATUS_INDEXING = "indexing"
STATUS_INDEXED = "indexed"
STATUS_ERROR_INDEXING = "error_indexing"


class SeedError(Exception):
    pass


def load_project_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(APP_ROOT / ".env", override=False)
    load_dotenv(APP_ROOT.parent / ".env", override=False)
    load_dotenv(Path.cwd() / ".env", override=False)


def resolve_docs_dir() -> Path:
    """定位 knowledge_docs 目录：环境变量优先，其次仓库根目录，再次 backend 下。"""
    candidates: list[Path] = []
    if env_dir := (os.getenv(DOCS_DIR_ENV) or "").strip():
        candidates.append(Path(env_dir))
    candidates.append(APP_ROOT.parent / "knowledge_docs")
    candidates.append(APP_ROOT / "knowledge_docs")

    for candidate in candidates:
        if candidate.is_dir() and list(candidate.glob("*.md")):
            return candidate
    searched = "、".join(str(path) for path in candidates)
    raise SeedError(
        f"未找到知识文档目录（需要包含 .md 文档），已检查：{searched}。可通过环境变量 {DOCS_DIR_ENV} 指定。"
    )


def resolve_embedding_model_spec() -> str:
    """选定 embedding 模型：环境变量指定 > 唯一可用模型；缺失或歧义时报错，不打印密钥。"""
    from yuxi.models.providers.cache import model_cache

    available = model_cache.get_all_specs("embedding")
    if not available:
        raise SeedError(
            "未配置可用的 embedding 模型：请先在「系统设置 → 模型配置」中启用一个 Embedding 模型"
            "（需 api 服务已启动以同步配置），或通过环境变量 "
            f"{EMBEDDING_SPEC_ENV} 指定。"
        )

    requested = (os.getenv(EMBEDDING_SPEC_ENV) or "").strip()
    if requested:
        info = model_cache.get_model_info(requested)
        if info is None or info.model_type != "embedding":
            specs = "、".join(item.spec for item in available)
            raise SeedError(
                f"{EMBEDDING_SPEC_ENV} 指定的模型不可用或不是 embedding 类型：{requested}。当前可用：{specs}"
            )
        return requested

    if len(available) == 1:
        return available[0].spec

    specs = "、".join(item.spec for item in available)
    raise SeedError(
        f"配置了 {len(available)} 个 embedding 模型（{specs}），"
        f"请通过环境变量 {EMBEDDING_SPEC_ENV} 指定本知识库使用哪一个。"
    )


def plan_document_action(status: str) -> str:
    """按库内文件状态决定动作：parse（含上传后首跑）/ index / skip；进行中与未知状态报错。"""
    if status in {STATUS_INDEXED, "done"}:
        return "skip"
    if status in {STATUS_PARSED, STATUS_ERROR_INDEXING}:
        return "index"
    if status in {STATUS_UPLOADED, STATUS_ERROR_PARSING, "failed"}:
        return "parse"
    if status in {STATUS_PARSING, STATUS_INDEXING}:
        raise SeedError(f"文件状态为 {status}，可能有另一个进程正在处理；请等它结束或排查残留状态后重试。")
    raise SeedError(f"未知的文件状态：{status}，请先排查知识库文件列表。")


def build_updated_agent_config(config_json: dict | None, kb_id: str) -> dict | None:
    """把 KB id 追加进 config_json.context.knowledges；已挂载返回 None，其余配置原样保留。"""
    config = dict(config_json or {})
    context = dict(config.get("context") or {})
    knowledges = list(context.get("knowledges") or [])
    if kb_id in knowledges:
        return None
    context["knowledges"] = knowledges + [kb_id]
    config["context"] = context
    return config


async def seed_knowledge_base(embedding_spec: str, docs_dir: Path) -> dict:
    from yuxi.knowledge import knowledge_base
    from yuxi.knowledge.utils import calculate_content_hash
    from yuxi.repositories.agent_repository import DEFAULT_AGENT_SLUG, AgentRepository
    from yuxi.repositories.knowledge_file_repository import KnowledgeFileRepository
    from yuxi.storage.minio.client import MinIOClient, aupload_file_to_minio
    from yuxi.storage.postgres.manager import pg_manager

    try:
        pg_manager.initialize()
        await pg_manager.create_business_tables()
        await pg_manager.ensure_business_schema()

        databases = (await knowledge_base.get_databases()).get("databases", [])
        existing_kb = next((db for db in databases if db.get("name") == KB_NAME), None)
        if existing_kb:
            kb_id = existing_kb["kb_id"]
        else:
            db_info = await knowledge_base.create_database(
                KB_NAME,
                KB_DESCRIPTION,
                kb_type=KB_TYPE,
                embedding_model_spec=embedding_spec,
                auto_generate_questions=False,
            )
            kb_id = db_info["kb_id"]

        summary = {"kb_id": kb_id, "kb_created": existing_kb is None, "ingested": [], "skipped": [], "mounted": False}
        file_repo = KnowledgeFileRepository()

        for doc_path in sorted(docs_dir.glob("*.md")):
            filename = doc_path.name
            records = await file_repo.list_same_name_files(kb_id=kb_id, filename=filename)

            if records:
                file_id = records[0].file_id
                action = plan_document_action(records[0].status or STATUS_UPLOADED)
            else:
                action = "upload"

            if action == "skip":
                summary["skipped"].append(filename)
                print(f"[跳过] {filename}（已入库）")
                continue

            if action == "upload":
                data = doc_path.read_bytes()
                content_hash = await calculate_content_hash(data)
                bucket = MinIOClient.KB_BUCKETS["documents"]
                object_name = f"{kb_id}/upload/{doc_path.stem}_{int(time.time() * 1000)}{doc_path.suffix}"
                minio_url = await aupload_file_to_minio(bucket, object_name, data)
                meta = await knowledge_base.add_file_record(
                    kb_id,
                    minio_url,
                    params={
                        "content_type": "file",
                        "content_hashes": {minio_url: content_hash},
                        "file_sizes": {minio_url: len(data)},
                    },
                    operator_id=OPERATOR_ID,
                )
                file_id = meta["file_id"]
                action = "parse"

            try:
                if action == "parse":
                    await asyncio.wait_for(
                        knowledge_base.parse_file(kb_id, file_id, operator_id=OPERATOR_ID),
                        PARSE_TIMEOUT_SECONDS,
                    )
                result = await asyncio.wait_for(
                    knowledge_base.index_file(kb_id, file_id, operator_id=OPERATOR_ID),
                    INDEX_TIMEOUT_SECONDS,
                )
            except TimeoutError as exc:
                raise SeedError(
                    f"{filename} 处理超时（解析上限 {PARSE_TIMEOUT_SECONDS}s / 入库上限 {INDEX_TIMEOUT_SECONDS}s），"
                    f"文件停在中间状态，请排查后重试。"
                ) from exc
            except Exception as exc:
                raise SeedError(f"{filename} 处理失败：{exc}") from exc

            final_status = result.get("status")
            if final_status != STATUS_INDEXED:
                raise SeedError(
                    f"{filename} 入库后状态为 {final_status}："
                    f"{result.get('error_message') or result.get('error') or '未知原因'}"
                )
            summary["ingested"].append(filename)
            print(f"[完成] {filename}")

        async with pg_manager.get_async_session_context() as session:
            repo = AgentRepository(session)
            agent = await repo.get_by_slug(DEFAULT_AGENT_SLUG)
            if agent is None:
                raise SeedError(f"默认智能体 {DEFAULT_AGENT_SLUG} 不存在：请先启动一次 api 服务生成后再执行本脚本。")
            updated_config = build_updated_agent_config(agent.config_json, kb_id)
            if updated_config is not None:
                await repo.update(agent, config_json=updated_config)
                summary["mounted"] = True

        return summary
    finally:
        await pg_manager.close()


def build_success_message(summary: dict) -> str:
    lines = [
        f"知识库「{KB_NAME}」就绪：kb_id={summary['kb_id']}（本次{'新建' if summary['kb_created'] else '复用已有'}）。",
    ]
    if summary["ingested"]:
        lines.append(f"入库 {len(summary['ingested'])} 份文档：{'、'.join(summary['ingested'])}。")
    if summary["skipped"]:
        lines.append(f"跳过 {len(summary['skipped'])} 份已入库文档：{'、'.join(summary['skipped'])}。")
    lines.append("已挂载到默认智能体。" if summary["mounted"] else "默认智能体此前已挂载，配置未改动。")
    return "\n".join(lines)


def main() -> int:
    load_project_env()
    try:
        docs_dir = resolve_docs_dir()
        embedding_spec = resolve_embedding_model_spec()
        summary = asyncio.run(seed_knowledge_base(embedding_spec, docs_dir))
    except SeedError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"初始化养老知识库失败：{exc}", file=sys.stderr)
        return 1

    print(build_success_message(summary))
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # pymilvus 的 MilvusKB.__del__ 在解释器退出阶段触发 gRPC channel.close()，
    # 其内部 join 通道线程在退出上下文中无法完成，进程会永久挂起（连接已由
    # 各阶段正常使用完毕、数据已落盘），直接终止以避免 make seed-kb 不返回。
    os._exit(code)
