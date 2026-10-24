"""养老知识库种子脚本的单元测试（不依赖真实服务）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import seed_knowledge_base

# ---------- resolve_embedding_model_spec ----------


class FakeModelInfo:
    def __init__(self, spec: str, model_type: str = "embedding"):
        self.spec = spec
        self.model_type = model_type


def _patch_model_cache(monkeypatch, all_specs, info_by_spec=None):
    from yuxi.models.providers.cache import model_cache

    monkeypatch.setattr(model_cache, "get_all_specs", lambda model_type=None: all_specs)
    monkeypatch.setattr(model_cache, "get_model_info", lambda spec: (info_by_spec or {}).get(spec))


def test_embedding_missing_fails_with_clear_message(monkeypatch):
    _patch_model_cache(monkeypatch, all_specs=[])
    monkeypatch.delenv(seed_knowledge_base.EMBEDDING_SPEC_ENV, raising=False)

    with pytest.raises(seed_knowledge_base.SeedError) as exc_info:
        seed_knowledge_base.resolve_embedding_model_spec()

    assert "embedding" in str(exc_info.value)
    assert "sk-" not in str(exc_info.value)


def test_embedding_single_available_is_auto_selected(monkeypatch):
    _patch_model_cache(monkeypatch, all_specs=[FakeModelInfo("siliconflow:bge-m3")])
    monkeypatch.delenv(seed_knowledge_base.EMBEDDING_SPEC_ENV, raising=False)

    assert seed_knowledge_base.resolve_embedding_model_spec() == "siliconflow:bge-m3"


def test_embedding_multiple_without_env_lists_specs(monkeypatch):
    _patch_model_cache(
        monkeypatch,
        all_specs=[FakeModelInfo("p1:m1"), FakeModelInfo("p2:m2")],
    )
    monkeypatch.delenv(seed_knowledge_base.EMBEDDING_SPEC_ENV, raising=False)

    with pytest.raises(seed_knowledge_base.SeedError) as exc_info:
        seed_knowledge_base.resolve_embedding_model_spec()

    message = str(exc_info.value)
    assert "p1:m1" in message and "p2:m2" in message
    assert seed_knowledge_base.EMBEDDING_SPEC_ENV in message


def test_embedding_env_var_picks_requested_spec(monkeypatch):
    _patch_model_cache(
        monkeypatch,
        all_specs=[FakeModelInfo("p1:m1"), FakeModelInfo("p2:m2")],
        info_by_spec={"p2:m2": FakeModelInfo("p2:m2")},
    )
    monkeypatch.setenv(seed_knowledge_base.EMBEDDING_SPEC_ENV, "p2:m2")

    assert seed_knowledge_base.resolve_embedding_model_spec() == "p2:m2"


def test_embedding_env_var_rejects_unknown_spec(monkeypatch):
    _patch_model_cache(monkeypatch, all_specs=[FakeModelInfo("p1:m1")])
    monkeypatch.setenv(seed_knowledge_base.EMBEDDING_SPEC_ENV, "ghost:model")

    with pytest.raises(seed_knowledge_base.SeedError) as exc_info:
        seed_knowledge_base.resolve_embedding_model_spec()

    assert "ghost:model" in str(exc_info.value)


# ---------- plan_document_action ----------


@pytest.mark.parametrize(
    "status,expected",
    [
        ("indexed", "skip"),
        ("done", "skip"),
        ("parsed", "index"),
        ("error_indexing", "index"),
        ("uploaded", "parse"),
        ("error_parsing", "parse"),
        ("failed", "parse"),
    ],
)
def test_plan_document_action_routes_statuses(status, expected):
    assert seed_knowledge_base.plan_document_action(status) == expected


@pytest.mark.parametrize("status", ["parsing", "indexing"])
def test_plan_document_action_rejects_in_progress(status):
    with pytest.raises(seed_knowledge_base.SeedError):
        seed_knowledge_base.plan_document_action(status)


def test_plan_document_action_rejects_unknown_status():
    with pytest.raises(seed_knowledge_base.SeedError):
        seed_knowledge_base.plan_document_action("weird-status")


# ---------- build_updated_agent_config ----------


def test_agent_config_appends_kb_and_keeps_other_fields():
    config = {"context": {"tools": ["family_tools"], "knowledges": ["kb_old"]}, "extra": 1}

    updated = seed_knowledge_base.build_updated_agent_config(config, "kb_new")

    assert updated["context"]["knowledges"] == ["kb_old", "kb_new"]
    assert updated["context"]["tools"] == ["family_tools"]
    assert updated["extra"] == 1


def test_agent_config_returns_none_when_already_mounted():
    config = {"context": {"knowledges": ["kb_new"]}}

    assert seed_knowledge_base.build_updated_agent_config(config, "kb_new") is None


def test_agent_config_works_on_empty_config():
    updated = seed_knowledge_base.build_updated_agent_config(None, "kb_new")

    assert updated["context"]["knowledges"] == ["kb_new"]


# ---------- resolve_docs_dir / main ----------


def test_resolve_docs_dir_reports_searched_paths(monkeypatch, tmp_path):
    monkeypatch.delenv(seed_knowledge_base.DOCS_DIR_ENV, raising=False)
    monkeypatch.setattr(seed_knowledge_base, "APP_ROOT", tmp_path / "backend")

    with pytest.raises(seed_knowledge_base.SeedError) as exc_info:
        seed_knowledge_base.resolve_docs_dir()

    assert seed_knowledge_base.DOCS_DIR_ENV in str(exc_info.value)


def test_resolve_docs_dir_uses_env_override(monkeypatch, tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "指南.md").write_text("内容", encoding="utf-8")
    monkeypatch.setenv(seed_knowledge_base.DOCS_DIR_ENV, str(docs_dir))

    assert seed_knowledge_base.resolve_docs_dir() == docs_dir


def test_main_fails_before_touching_services_when_embedding_missing(monkeypatch, capsys):
    _patch_model_cache(monkeypatch, all_specs=[])
    monkeypatch.delenv(seed_knowledge_base.EMBEDDING_SPEC_ENV, raising=False)
    monkeypatch.setattr(seed_knowledge_base, "load_project_env", lambda: None)
    monkeypatch.setattr(seed_knowledge_base, "resolve_docs_dir", lambda: Path("docs"))

    def fail_if_seeded(*_args, **_kwargs):
        raise AssertionError("缺少 embedding 配置时不应进入种子流程")

    monkeypatch.setattr(seed_knowledge_base, "seed_knowledge_base", fail_if_seeded)

    assert seed_knowledge_base.main() == 1
    assert "embedding" in capsys.readouterr().err


def test_success_message_contains_no_secrets():
    message = seed_knowledge_base.build_success_message(
        {
            "kb_id": "kb_1234567890",
            "kb_created": True,
            "ingested": ["老年慢性病日常管理指南.md"],
            "skipped": [],
            "mounted": True,
        }
    )

    assert "kb_1234567890" in message
    assert "老年慢性病日常管理指南.md" in message
    assert "已挂载" in message
