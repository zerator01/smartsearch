import json
import asyncio
from smart_search import cli
from smart_search import skill_installer


class GbkStdout:
    encoding = "gbk"
    errors = "strict"

    def __init__(self):
        self.parts = []

    def write(self, text):
        text.encode(self.encoding, errors=self.errors)
        self.parts.append(text)
        return len(text)

    def getvalue(self):
        return "".join(self.parts)


def test_help_contains_commands(capsys):
    try:
        cli.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "search" in out
    assert "doctor" in out
    assert "regression" in out


def test_version_flags_exit_successfully(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_get_version", lambda: "9.9.9-test")

    for flag in ["--version", "--v", "-v"]:
        try:
            cli.main([flag])
        except SystemExit as exc:
            assert exc.code == 0

        assert capsys.readouterr().out.strip() == "smart-search 9.9.9-test"


def test_each_subcommand_help_exits_successfully(capsys):
    commands = [
        ["search", "--help"],
        ["fetch", "--help"],
        ["map", "--help"],
        ["exa-search", "--help"],
        ["exa-similar", "--help"],
        ["zhipu-search", "--help"],
        ["context7-library", "--help"],
        ["context7-docs", "--help"],
        ["smoke", "--help"],
        ["doctor", "--help"],
        ["setup", "--help"],
        ["config", "--help"],
        ["config", "path", "--help"],
        ["config", "list", "--help"],
        ["config", "set", "--help"],
        ["config", "unset", "--help"],
        ["model", "--help"],
        ["model", "set", "--help"],
        ["model", "current", "--help"],
        ["regression", "--help"],
    ]

    for command in commands:
        try:
            cli.main(command)
        except SystemExit as exc:
            assert exc.code == 0

    out = capsys.readouterr().out
    assert "usage: smart-search search" in out
    assert "usage: smart-search regression" in out


def test_command_aliases_parse_to_canonical_commands():
    parser = cli.build_parser()

    command_cases = [
        (["s", "query"], "search"),
        (["f", "https://example.com"], "fetch"),
        (["m", "https://example.com"], "map"),
        (["exa", "query"], "exa-search"),
        (["x", "query"], "exa-search"),
        (["xs", "https://example.com"], "exa-similar"),
        (["z", "query"], "zhipu-search"),
        (["zp", "query"], "zhipu-search"),
        (["c7", "react"], "context7-library"),
        (["ctx7", "react"], "context7-library"),
        (["c7d", "/facebook/react", "hooks"], "context7-docs"),
        (["c7docs", "/facebook/react", "hooks"], "context7-docs"),
        (["ctx7-docs", "/facebook/react", "hooks"], "context7-docs"),
        (["sm"], "smoke"),
        (["d"], "doctor"),
        (["init", "--non-interactive"], "setup"),
        (["cfg", "ls"], "config"),
        (["mdl", "cur"], "model"),
        (["reg"], "regression"),
    ]

    for argv, command in command_cases:
        assert parser.parse_args(argv).command == command

    config_cases = [
        (["cfg", "p"], "path"),
        (["cfg", "ls"], "list"),
        (["cfg", "l"], "list"),
        (["cfg", "s", "SMART_SEARCH_MODEL", "grok"], "set"),
        (["cfg", "rm", "SMART_SEARCH_MODEL"], "unset"),
        (["cfg", "u", "SMART_SEARCH_MODEL"], "unset"),
    ]
    for argv, config_command in config_cases:
        assert parser.parse_args(argv).config_command == config_command

    model_cases = [
        (["mdl", "s", "grok"], "set"),
        (["mdl", "cur"], "current"),
        (["mdl", "c"], "current"),
    ]
    for argv, model_command in model_cases:
        assert parser.parse_args(argv).model_command == model_command


def test_search_help_exposes_timeout(capsys):
    try:
        cli.main(["search", "--help"])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "--timeout SECONDS" in out


def test_search_outputs_json_and_file(monkeypatch, capsys):
    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        return {
            "ok": True,
            "query": query,
            "content": "Answer",
            "sources": [{"url": "https://example.com", "title": "Example"}],
            "sources_count": 1,
        }

    monkeypatch.setattr(cli.service, "search", fake_search)
    written = {}

    def fake_write_output(path, content):
        written["path"] = path
        written["content"] = content

    monkeypatch.setattr(cli.service, "write_output", fake_write_output)
    output = "C:/tmp/smart-search-cli-test-result.json"

    code = cli.main(["search", "query", "--output", output])

    assert code == cli.EXIT_OK
    stdout_data = json.loads(capsys.readouterr().out)
    file_data = json.loads(written["content"])
    assert written["path"] == output
    assert stdout_data["sources_count"] == 1
    assert file_data["content"] == "Answer"


def test_search_json_outputs_readable_chinese(monkeypatch, capsys):
    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        return {"ok": True, "content": "中文NBA战报", "sources": [], "sources_count": 0}

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main(["search", "nba战报", "--format", "json"])

    assert code == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "中文NBA战报" in out
    assert "\\u4e2d\\u6587" not in out
    assert json.loads(out)["content"] == "中文NBA战报"


def test_search_content_format_outputs_content_only(monkeypatch, capsys):
    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        return {"ok": True, "content": "中文NBA战报", "sources": [{"url": "https://example.com"}], "sources_count": 1}

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main(["search", "nba战报", "--format", "content"])

    assert code == cli.EXIT_OK
    assert capsys.readouterr().out == "中文NBA战报\n"


def test_fetch_content_format_matches_markdown_body(monkeypatch, capsys):
    async def fake_fetch(url):
        return {"ok": True, "url": url, "content": "# 中文页面"}

    monkeypatch.setattr(cli.service, "fetch", fake_fetch)

    content_code = cli.main(["fetch", "https://example.com", "--format", "content"])
    content_out = capsys.readouterr().out
    markdown_code = cli.main(["fetch", "https://example.com", "--format", "markdown"])
    markdown_out = capsys.readouterr().out

    assert content_code == cli.EXIT_OK
    assert markdown_code == cli.EXIT_OK
    assert content_out == "# 中文页面\n"
    assert markdown_out == content_out


def test_context7_docs_content_format_outputs_content(monkeypatch, capsys):
    async def fake_context7_docs(library_id, query):
        return {"ok": True, "provider": "context7-docs", "library_id": library_id, "query": query, "content": "中文文档内容"}

    monkeypatch.setattr(cli.service, "context7_docs", fake_context7_docs)

    code = cli.main(["context7-docs", "/facebook/react", "hooks", "--format", "content"])

    assert code == cli.EXIT_OK
    assert capsys.readouterr().out == "中文文档内容\n"


def test_search_alias_uses_canonical_command(monkeypatch, capsys):
    captured = {}

    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        captured["query"] = query
        return {"ok": True, "content": "Answer", "sources": [], "sources_count": 0}

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main(["s", "alias query"])

    assert code == cli.EXIT_OK
    assert captured["query"] == "alias query"
    assert json.loads(capsys.readouterr().out)["content"] == "Answer"


def test_fetch_alias_uses_canonical_command(monkeypatch, capsys):
    async def fake_fetch(url):
        return {"ok": True, "url": url, "content": "Page"}

    monkeypatch.setattr(cli.service, "fetch", fake_fetch)

    code = cli.main(["f", "https://example.com"])

    assert code == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["url"] == "https://example.com"


def test_doctor_alias_uses_canonical_command(monkeypatch, capsys):
    async def fake_doctor():
        return {"ok": True, "config_status": "ok"}

    monkeypatch.setattr(cli.service, "doctor", fake_doctor)

    code = cli.main(["d"])

    assert code == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["config_status"] == "ok"


def test_search_timeout_outputs_json_and_exit_4(monkeypatch, capsys):
    async def slow_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        await asyncio.sleep(1)
        return {
            "ok": True,
            "query": query,
            "content": "late answer",
            "sources": [{"url": "https://example.com"}],
            "sources_count": 1,
        }

    monkeypatch.setattr(cli.service, "search", slow_search)

    code = cli.main(["search", "slow query", "--timeout", "0.01", "--format", "markdown"])

    assert code == cli.EXIT_NETWORK_ERROR
    out = capsys.readouterr()
    data = json.loads(out.out)
    assert out.err == ""
    assert data["ok"] is False
    assert data["error_type"] == "network_error"
    assert "0.01" in data["error"]
    assert "seconds" in data["error"]
    assert data["query"] == "slow query"
    assert data["content"] == ""
    assert data["sources"] == []
    assert data["sources_count"] == 0
    assert data["primary_sources"] == []
    assert data["primary_sources_count"] == 0
    assert data["extra_sources"] == []
    assert data["extra_sources_count"] == 0
    assert data["source_warning"] == ""


def test_markdown_search_includes_sources(monkeypatch, capsys):
    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        return {
            "ok": True,
            "content": "Answer",
            "sources": [{"url": "https://example.com", "title": "Example"}],
            "sources_count": 1,
        }

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main(["search", "query", "--format", "markdown"])

    assert code == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "Answer" in out
    assert "[Example](https://example.com)" in out


def test_markdown_search_labels_primary_and_extra_sources(monkeypatch, capsys):
    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        return {
            "ok": True,
            "content": "Answer",
            "primary_sources": [{"url": "https://primary.example.com", "title": "Primary"}],
            "primary_sources_count": 1,
            "extra_sources": [{"url": "https://extra.example.com", "title": "Extra"}],
            "extra_sources_count": 1,
            "sources": [
                {"url": "https://primary.example.com", "title": "Primary"},
                {"url": "https://extra.example.com", "title": "Extra"},
            ],
            "sources_count": 2,
            "source_warning": "extra_sources are retrieved in parallel",
        }

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main(["search", "query", "--format", "markdown"])

    assert code == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "## Primary Sources" in out
    assert "[Primary](https://primary.example.com)" in out
    assert "## Extra Sources" in out
    assert "[Extra](https://extra.example.com)" in out
    assert "extra_sources are retrieved in parallel" in out


def test_config_error_exit_code(monkeypatch, capsys):
    async def fake_doctor():
        return {"ok": False, "error_type": "config_error", "SMART_SEARCH_API_KEY": "未配置"}

    monkeypatch.setattr(cli.service, "doctor", fake_doctor)

    code = cli.main(["doctor"])

    assert code == cli.EXIT_CONFIG_ERROR
    assert json.loads(capsys.readouterr().out)["SMART_SEARCH_API_KEY"] == "未配置"


def test_network_error_exit_code(monkeypatch, capsys):
    async def fake_fetch(url):
        return {"ok": False, "error_type": "network_error", "error": "upstream timeout", "url": url}

    monkeypatch.setattr(cli.service, "fetch", fake_fetch)

    code = cli.main(["fetch", "https://example.com"])

    assert code == cli.EXIT_NETWORK_ERROR
    assert json.loads(capsys.readouterr().out)["error"] == "upstream timeout"


def test_stdout_falls_back_for_gbk_unencodable_unicode(monkeypatch):
    fake_stdout = GbkStdout()
    monkeypatch.setattr(cli.sys, "stdout", fake_stdout)

    code = cli._print_result("exa-search", {"ok": True, "content": "A\u2060B"}, "json")

    assert code == cli.EXIT_OK
    out = fake_stdout.getvalue()
    assert "\\u2060" in out
    assert json.loads(out)["content"] == "A\u2060B"


def test_gbk_stdout_keeps_json_parseable_with_chinese_and_unencodable_unicode(monkeypatch):
    fake_stdout = GbkStdout()
    monkeypatch.setattr(cli.sys, "stdout", fake_stdout)

    code = cli._print_result("search", {"ok": True, "content": "中文A\u2060B📅"}, "json")

    assert code == cli.EXIT_OK
    out = fake_stdout.getvalue()
    assert "中文" in out
    assert "\\u2060" in out
    assert "\\ud83d\\udcc5" in out
    assert json.loads(out)["content"] == "中文A\u2060B📅"


def test_real_doctor_missing_primary_url_returns_config_exit(monkeypatch, capsys):
    secret = "placeholder-test-secret"
    monkeypatch.delenv("SMART_SEARCH_API_URL", raising=False)
    monkeypatch.setenv("SMART_SEARCH_API_KEY", secret)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    code = cli.main(["doctor"])

    out = capsys.readouterr().out
    data = json.loads(out)
    assert code == cli.EXIT_CONFIG_ERROR
    assert data["ok"] is False
    assert data["error_type"] == "config_error"
    assert secret not in out


def test_model_set_uses_service(monkeypatch, capsys):
    def fake_set_model(model):
        return {"ok": True, "previous_model": "old", "current_model": model, "config_file": "C:/tmp/smart-search-config.json"}

    monkeypatch.setattr(cli.service, "set_model", fake_set_model)

    code = cli.main(["model", "set", "grok-4-fast"])

    assert code == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["current_model"] == "grok-4-fast"


def test_model_aliases_use_canonical_commands(monkeypatch, capsys):
    def fake_current_model():
        return {"ok": True, "current_model": "grok-4-fast"}

    def fake_set_model(model):
        return {"ok": True, "current_model": model}

    monkeypatch.setattr(cli.service, "current_model", fake_current_model)
    monkeypatch.setattr(cli.service, "set_model", fake_set_model)

    assert cli.main(["mdl", "cur"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["current_model"] == "grok-4-fast"
    assert cli.main(["mdl", "s", "grok-4-fast"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["current_model"] == "grok-4-fast"


def test_config_set_masks_value(monkeypatch, capsys):
    def fake_config_set(key, value):
        return {"ok": True, "key": key, "value": "sk-t********cret", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)

    code = cli.main(["config", "set", "SMART_SEARCH_API_KEY", "sk-test-secret"])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert "sk-test-secret" not in out
    assert json.loads(out)["value"] == "sk-t********cret"


def test_config_list_does_not_request_secrets(monkeypatch, capsys):
    captured = {}

    def fake_config_list(show_secrets=False):
        captured["show_secrets"] = show_secrets
        return {"ok": True, "values": {"SMART_SEARCH_API_KEY": "sk-t********cret"}}

    monkeypatch.setattr(cli.service, "config_list", fake_config_list)

    code = cli.main(["config", "list"])

    assert code == cli.EXIT_OK
    assert captured["show_secrets"] is False
    assert json.loads(capsys.readouterr().out)["values"]["SMART_SEARCH_API_KEY"].endswith("cret")


def test_config_aliases_use_canonical_commands(monkeypatch, capsys):
    captured = {}

    def fake_config_list(show_secrets=False):
        captured["show_secrets"] = show_secrets
        return {"ok": True, "values": {"SMART_SEARCH_MODEL": "grok"}}

    def fake_config_set(key, value):
        captured["set"] = (key, value)
        return {"ok": True, "key": key, "value": value}

    def fake_config_unset(key):
        captured["unset"] = key
        return {"ok": True, "key": key}

    monkeypatch.setattr(cli.service, "config_list", fake_config_list)
    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_unset", fake_config_unset)

    assert cli.main(["cfg", "ls"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["values"]["SMART_SEARCH_MODEL"] == "grok"
    assert captured["show_secrets"] is False

    assert cli.main(["cfg", "s", "SMART_SEARCH_MODEL", "grok-4-fast"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["value"] == "grok-4-fast"
    assert captured["set"] == ("SMART_SEARCH_MODEL", "grok-4-fast")

    assert cli.main(["cfg", "rm", "SMART_SEARCH_MODEL"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["key"] == "SMART_SEARCH_MODEL"
    assert captured["unset"] == "SMART_SEARCH_MODEL"


def test_setup_non_interactive_saves_values(monkeypatch, capsys):
    saved = {}

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})

    code = cli.main([
        "setup",
        "--non-interactive",
        "--api-url",
        "https://api.example.com/v1",
        "--api-key",
        "sk-test-secret",
        "--api-mode",
        "chat-completions",
        "--xai-tools",
        "web_search",
        "--model",
        "test-model",
        "--xai-api-key",
        "xai-test-secret",
        "--xai-model",
        "xai-model",
        "--openai-compatible-api-url",
        "https://relay.example.com/v1",
        "--openai-compatible-api-key",
        "relay-test-secret",
        "--openai-compatible-model",
        "relay-model",
        "--validation-level",
        "balanced",
        "--fallback-mode",
        "auto",
        "--minimum-profile",
        "standard",
        "--zhipu-key",
        "zhipu-secret",
        "--context7-key",
        "ctx-secret",
        "--tavily-api-url",
        "pool.example.com",
        "--tavily-key",
        "th-test-secret",
        "--firecrawl-api-url",
        "firecrawl.example.com/v2",
        "--firecrawl-key",
        "firecrawl-secret",
    ])

    out = capsys.readouterr().out
    assert code == cli.EXIT_OK
    assert saved["SMART_SEARCH_API_URL"] == "https://api.example.com/v1"
    assert saved["SMART_SEARCH_API_KEY"] == "sk-test-secret"
    assert saved["SMART_SEARCH_API_MODE"] == "chat-completions"
    assert saved["SMART_SEARCH_XAI_TOOLS"] == "web_search"
    assert saved["SMART_SEARCH_MODEL"] == "test-model"
    assert saved["XAI_API_KEY"] == "xai-test-secret"
    assert saved["XAI_MODEL"] == "xai-model"
    assert saved["OPENAI_COMPATIBLE_API_URL"] == "https://relay.example.com/v1"
    assert saved["OPENAI_COMPATIBLE_API_KEY"] == "relay-test-secret"
    assert saved["OPENAI_COMPATIBLE_MODEL"] == "relay-model"
    assert saved["SMART_SEARCH_VALIDATION_LEVEL"] == "balanced"
    assert saved["SMART_SEARCH_FALLBACK_MODE"] == "auto"
    assert saved["SMART_SEARCH_MINIMUM_PROFILE"] == "standard"
    assert saved["ZHIPU_API_KEY"] == "zhipu-secret"
    assert saved["CONTEXT7_API_KEY"] == "ctx-secret"
    assert saved["TAVILY_API_URL"] == "https://pool.example.com/api/tavily"
    assert saved["TAVILY_API_KEY"] == "th-test-secret"
    assert saved["FIRECRAWL_API_URL"] == "https://firecrawl.example.com/v2"
    assert saved["FIRECRAWL_API_KEY"] == "firecrawl-secret"
    assert "sk-test-secret" not in out
    assert "th-test-secret" not in out


def test_setup_non_interactive_installs_selected_skills(monkeypatch, tmp_path, capsys):
    saved = {}

    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})

    code = cli.main([
        "setup",
        "--non-interactive",
        "--install-skills",
        "codex,claude,cursor",
        "--skills-root",
        str(tmp_path),
    ])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_OK
    assert saved == {}
    assert data["skills"]["installed_count"] == 3
    assert (tmp_path / ".agents" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    assert (tmp_path / ".claude" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    assert (tmp_path / ".cursor" / "skills" / "smart-search-cli" / "SKILL.md").is_file()


def test_setup_skip_skills_writes_no_skill_files(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})

    code = cli.main([
        "setup",
        "--non-interactive",
        "--skip-skills",
        "--install-skills",
        "codex",
        "--skills-root",
        str(tmp_path),
    ])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_OK
    assert "skills" not in data
    assert not (tmp_path / ".agents" / "skills" / "smart-search-cli").exists()


def test_setup_unknown_skill_target_returns_parameter_error(monkeypatch, capsys):
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})

    code = cli.main(["setup", "--non-interactive", "--install-skills", "unknown"])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_PARAMETER_ERROR
    assert data["error_type"] == "parameter_error"
    assert "Unknown skill target" in data["error"]


def test_setup_guided_installs_tui_selected_skill_targets(monkeypatch, tmp_path, capsys):
    saved = {}
    answers = iter(["skip", "skip", "skip", "n"])
    checkbox_calls = []

    def fake_checkbox(message, choices):
        checkbox_calls.append(message)
        if "AI tools" in message:
            return ["codex", "cursor"]
        return []

    monkeypatch.setattr(cli, "_checkbox_with_tui", fake_checkbox)
    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    code = cli.main(["setup", "--lang", "en", "--skills-root", str(tmp_path)])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert code == cli.EXIT_OK
    assert data["skills"]["installed_count"] == 2
    assert (tmp_path / ".agents" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    assert (tmp_path / ".cursor" / "skills" / "smart-search-cli" / "SKILL.md").is_file()
    assert "Install the smart-search-cli skill" in captured.err
    assert "Skill install result" in captured.err


def test_setup_banner_falls_back_when_pyfiglet_unavailable(monkeypatch, capsys):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "pyfiglet":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    cli._write_setup_banner("en")
    captured = capsys.readouterr()

    assert "Smart Search" in captured.err
    assert "CLI-first multi-source search" in captured.err


def test_skill_installer_parse_aliases_and_all(tmp_path):
    assert skill_installer.parse_skill_targets("claude-code,github-copilot,agentskills") == [
        "claude",
        "copilot",
        "codex",
    ]
    assert len(skill_installer.parse_skill_targets("all")) == len(skill_installer.SKILL_TARGETS)

    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text("---\nname: smart-search-cli\n---\n", encoding="utf-8")
    result = skill_installer.install_skill_targets(
        ["codex"],
        project_root=tmp_path / "project",
        source_root=source,
    )

    assert result["ok"] is True
    assert result["installed_count"] == 1
    assert (tmp_path / "project" / ".agents" / "skills" / "smart-search-cli" / "SKILL.md").is_file()


def test_tavily_url_normalization_cases():
    cases = {
        "pool.example.com": "https://pool.example.com/api/tavily",
        "https://pool.example.com": "https://pool.example.com/api/tavily",
        "https://pool.example.com/mcp": "https://pool.example.com/api/tavily",
        "https://pool.example.com/api/tavily": "https://pool.example.com/api/tavily",
        "https://api.tavily.com": "https://api.tavily.com",
    }

    for raw, expected in cases.items():
        assert cli._normalize_tavily_api_url(raw) == expected
    assert cli._normalize_tavily_api_url("https://custom.example.com", hikari=False) == "https://custom.example.com"
    assert cli._normalize_tavily_flag_api_url("https://custom.example.com", "tvly-key") == "https://custom.example.com"
    assert cli._normalize_tavily_flag_api_url("https://custom.example.com/mcp", "tvly-key") == "https://custom.example.com/api/tavily"
    assert cli._normalize_tavily_flag_api_url("https://custom.example.com", "th-key") == "https://custom.example.com/api/tavily"


def test_tavily_hikari_key_recommends_hikari_endpoint(monkeypatch):
    values = {"TAVILY_API_KEY": "th-test-secret"}
    seen = {}

    def fake_prompt_select(message, choices, default):
        seen["default"] = default
        return "hikari"

    monkeypatch.setattr(cli, "_prompt_select", fake_prompt_select)
    monkeypatch.setattr(cli, "_prompt_value", lambda *args, **kwargs: "https://pool.example.com/mcp")

    cli._prompt_tavily_api_url(values, {}, "en")

    assert seen["default"] == "hikari"
    assert values["TAVILY_API_URL"] == "https://pool.example.com/api/tavily"


def test_tavily_hikari_prompt_shows_beginner_url_example(monkeypatch, capsys):
    values = {"TAVILY_API_KEY": "th-test-secret"}

    monkeypatch.setattr(cli, "_prompt_select", lambda message, choices, default: "hikari")
    monkeypatch.setattr(cli, "_prompt_value", lambda *args, **kwargs: "https://pool.example.com")

    cli._prompt_tavily_api_url(values, {}, "zh")
    captured = capsys.readouterr()

    assert values["TAVILY_API_URL"] == "https://pool.example.com/api/tavily"
    assert "例如 https://pool.example.com" in captured.err
    assert "api/tavily" in captured.err


def test_setup_guided_zh_groups_minimum_capabilities(monkeypatch, capsys):
    saved = {}
    answers = iter(["xai", "", "exa", "tavily", "", "n", "n"])
    secrets = iter(["xai-test-secret", "exa-test-secret", "tavily-test-secret"])

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(secrets))

    code = cli.main(["setup", "--skip-skills", "--lang", "zh"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert code == cli.EXIT_OK
    assert saved == {
        "XAI_API_KEY": "xai-test-secret",
        "EXA_API_KEY": "exa-test-secret",
        "TAVILY_API_URL": "https://api.tavily.com",
        "TAVILY_API_KEY": "tavily-test-secret",
    }
    assert data["minimum_profile_ok"] is True
    assert data["minimum_profile_missing"] == []
    assert captured.out.lstrip().startswith("{")
    assert "Smart Search" in captured.err
    assert "不知道怎么填" in captured.err
    assert "main_search + docs_search + web_fetch" in captured.err
    assert "[1/3" in captured.err
    assert "main_search" in captured.err
    assert "pool.example.com" not in captured.out
    assert "xai-test-secret" not in captured.err
    assert "xai-test-secret" not in captured.out


def test_setup_guided_uses_tui_defaults_for_configured_providers(monkeypatch, capsys):
    current = {
        "OPENAI_COMPATIBLE_API_URL": "https://relay.example.com/v1",
        "OPENAI_COMPATIBLE_API_KEY": "relay-old-secret",
        "CONTEXT7_API_KEY": "ctx-old-secret",
        "FIRECRAWL_API_KEY": "firecrawl-old-secret",
        "FIRECRAWL_API_URL": "https://firecrawl.example.com/v2",
    }
    saved = {}
    checkbox_calls = []

    def fake_checkbox(message, choices):
        selected = [choice["value"] for choice in choices if choice.get("enabled")]
        checkbox_calls.append((message, selected))
        return selected

    monkeypatch.setattr(cli, "_checkbox_with_tui", fake_checkbox)
    monkeypatch.setattr(cli, "_select_with_tui", lambda message, choices, default=None: default)
    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": {**current, **saved}})
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "")

    code = cli.main(["setup", "--skip-skills", "--lang", "en"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert code == cli.EXIT_OK
    assert data["minimum_profile_ok"] is True
    assert saved == {}
    assert "https://relay.example.com/v1" not in captured.err
    assert "https://firecrawl.example.com/v2" not in captured.err
    assert "configured" in captured.err
    assert checkbox_calls[:3] == [
        ("Choose main_search providers", ["openai-compatible"]),
        ("Choose docs_search providers", ["context7"]),
        ("Choose web_fetch providers", ["firecrawl"]),
    ]


def test_setup_guided_en_reports_missing_minimum(monkeypatch, capsys):
    saved = {}
    answers = iter(["skip", "skip", "skip", "n", "n"])

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    code = cli.main(["setup", "--skip-skills", "--lang", "en"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert code == cli.EXIT_OK
    assert saved == {}
    assert data["minimum_profile_ok"] is False
    assert data["minimum_profile_missing"] == ["main_search", "docs_search", "web_fetch"]
    assert "Smart Search setup wizard" in captured.err
    assert "If unsure" in captured.err
    assert "main_search + docs_search + web_fetch" in captured.err
    assert "[MISSING] main_search primary search" in captured.err
    assert "will fail closed" in captured.err
    assert "your-relay.example.com" not in captured.out


def test_setup_guided_masks_configured_url_defaults(monkeypatch, capsys):
    current = {
        "OPENAI_COMPATIBLE_API_URL": "https://private-relay.example.com/v1",
        "OPENAI_COMPATIBLE_API_KEY": "relay-old-secret",
    }
    answers = iter(["openai", "", "", "skip", "skip", "n", "n"])
    secrets = iter([""])

    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "key": key, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": current.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(secrets))

    code = cli.main(["setup", "--skip-skills", "--lang", "en"])
    captured = capsys.readouterr()

    assert code == cli.EXIT_OK
    assert "https://private-relay.example.com/v1" not in captured.err
    assert "configured, press Enter to keep" in captured.err


def test_setup_guided_main_search_can_save_openai_compatible_peer(monkeypatch, capsys):
    saved = {}
    answers = iter(["openai", "https://relay.example.com/v1", "", "skip", "skip", "n", "n"])
    secrets = iter(["relay-test-secret"])

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(secrets))

    code = cli.main(["setup", "--skip-skills", "--lang", "en"])
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert code == cli.EXIT_OK
    assert saved == {
        "OPENAI_COMPATIBLE_API_URL": "https://relay.example.com/v1",
        "OPENAI_COMPATIBLE_API_KEY": "relay-test-secret",
    }
    assert data["capability_status"]["main_search"]["configured"] == ["openai-compatible"]
    assert data["minimum_profile_missing"] == ["docs_search", "web_fetch"]
    assert "relay-test-secret" not in captured.out
    assert "relay-test-secret" not in captured.err


def test_setup_guided_main_search_can_save_both_peer_providers(monkeypatch, capsys):
    saved = {}
    answers = iter(["both", "", "https://relay.example.com/v1", "", "skip", "skip", "n", "n"])
    secrets = iter(["xai-test-secret", "relay-test-secret"])

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(secrets))

    code = cli.main(["setup", "--skip-skills", "--lang", "en"])
    data = json.loads(capsys.readouterr().out)

    assert code == cli.EXIT_OK
    assert saved == {
        "XAI_API_KEY": "xai-test-secret",
        "OPENAI_COMPATIBLE_API_URL": "https://relay.example.com/v1",
        "OPENAI_COMPATIBLE_API_KEY": "relay-test-secret",
    }
    assert data["capability_status"]["main_search"]["configured"] == ["xai-responses", "openai-compatible"]
    assert data["capability_status"]["main_search"]["fallback_chain"] == ["xai-responses", "openai-compatible"]


def test_setup_interactive_language_prompt(monkeypatch, capsys):
    saved = {}
    answers = iter(["en", "skip", "skip", "skip", "n", "n"])

    monkeypatch.setattr(cli.service, "config_set", lambda key, value: {"ok": True, "value": "***"})
    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(cli.service, "config_list", lambda show_secrets=False: {"ok": True, "values": saved.copy()})
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    code = cli.main(["setup", "--skip-skills"])
    captured = capsys.readouterr()

    assert code == cli.EXIT_OK
    assert "Smart Search setup wizard" in captured.err


def test_search_passes_routing_options(monkeypatch, capsys):
    captured = {}

    async def fake_search(query, platform="", model="", extra_sources=0, validation="", fallback="", providers="auto"):
        captured.update({"validation": validation, "fallback": fallback, "providers": providers})
        return {"ok": True, "content": "Answer", "sources": [], "sources_count": 0}

    monkeypatch.setattr(cli.service, "search", fake_search)

    code = cli.main([
        "search",
        "query",
        "--validation",
        "strict",
        "--fallback",
        "off",
        "--providers",
        "grok,zhipu",
    ])

    assert code == cli.EXIT_OK
    assert captured == {"validation": "strict", "fallback": "off", "providers": "grok,zhipu"}
    assert json.loads(capsys.readouterr().out)["content"] == "Answer"


def test_smoke_command_uses_service(monkeypatch, capsys):
    async def fake_smoke(mode="mock"):
        return {"ok": True, "mode": mode, "failed_cases": [], "cases": []}

    monkeypatch.setattr(cli.service, "smoke", fake_smoke)

    code = cli.main(["smoke", "--mode", "mock"])

    assert code == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["mode"] == "mock"


def test_provider_and_smoke_aliases_use_canonical_commands(monkeypatch, capsys):
    async def fake_exa_search(*args, **kwargs):
        return {"ok": True, "provider": "exa"}

    async def fake_zhipu_search(*args, **kwargs):
        return {"ok": True, "provider": "zhipu"}

    async def fake_context7_library(*args, **kwargs):
        return {"ok": True, "provider": "context7-library"}

    async def fake_context7_docs(*args, **kwargs):
        return {"ok": True, "provider": "context7-docs"}

    async def fake_smoke(mode="mock"):
        return {"ok": True, "mode": mode, "failed_cases": [], "cases": []}

    monkeypatch.setattr(cli.service, "exa_search", fake_exa_search)
    monkeypatch.setattr(cli.service, "zhipu_search", fake_zhipu_search)
    monkeypatch.setattr(cli.service, "context7_library", fake_context7_library)
    monkeypatch.setattr(cli.service, "context7_docs", fake_context7_docs)
    monkeypatch.setattr(cli.service, "smoke", fake_smoke)

    assert cli.main(["exa", "query"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["provider"] == "exa"
    assert cli.main(["z", "query"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["provider"] == "zhipu"
    assert cli.main(["c7", "react"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["provider"] == "context7-library"
    assert cli.main(["c7docs", "/facebook/react", "hooks"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["provider"] == "context7-docs"
    assert cli.main(["sm"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["mode"] == "mock"


def test_smoke_command_accepts_mock_and_live_flags(monkeypatch, capsys):
    captured = []

    async def fake_smoke(mode="mock"):
        captured.append(mode)
        return {"ok": True, "mode": mode, "failed_cases": [], "cases": []}

    monkeypatch.setattr(cli.service, "smoke", fake_smoke)

    assert cli.main(["smoke", "--mock"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["mode"] == "mock"
    assert cli.main(["smoke", "--live"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["mode"] == "live"
    assert captured == ["mock", "live"]


def test_setup_interactive_does_not_print_current_secret(monkeypatch, capsys):
    prompts = []

    def fake_config_set(key, value):
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    def fake_input(prompt):
        prompts.append(prompt)
        return ""

    def fake_getpass(prompt):
        prompts.append(prompt)
        return ""

    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(
        cli.service,
        "config_list",
        lambda show_secrets=False: {
            "ok": True,
            "values": {
                "SMART_SEARCH_API_URL": "https://api.example.com/v1",
                "SMART_SEARCH_API_KEY": "sk-test-secret",
                "SMART_SEARCH_MODEL": "test-model",
                "EXA_API_KEY": "exa-test-secret",
            },
        },
    )
    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli.getpass, "getpass", fake_getpass)

    code = cli.main(["setup", "--advanced", "--lang", "en"])
    captured = capsys.readouterr()
    prompt_text = "\n".join(prompts)

    assert code == cli.EXIT_OK
    assert "sk-test-secret" not in captured.out
    assert "sk-test-secret" not in captured.err
    assert "sk-test-secret" not in prompt_text
    assert "exa-test-secret" not in prompt_text
    assert "Legacy primary API key optional [configured, press Enter to keep]" in prompt_text


def test_setup_advanced_mode_keeps_low_level_prompts(monkeypatch, capsys):
    prompts = []
    saved = {}

    def fake_config_set(key, value):
        saved[key] = value
        return {"ok": True, "key": key, "value": "***", "config_file": "C:/tmp/config.json"}

    def fake_input(prompt):
        prompts.append(prompt)
        return ""

    def fake_getpass(prompt):
        prompts.append(prompt)
        return ""

    monkeypatch.setattr(cli.service, "config_path", lambda: {"ok": True, "config_file": "C:/tmp/config.json"})
    monkeypatch.setattr(
        cli.service,
        "config_list",
        lambda show_secrets=False: {"ok": True, "values": {"SMART_SEARCH_API_URL": "https://api.example.com/v1"}},
    )
    monkeypatch.setattr(cli.service, "config_set", fake_config_set)
    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(cli.getpass, "getpass", fake_getpass)

    code = cli.main(["setup", "--advanced", "--lang", "en"])

    assert code == cli.EXIT_OK
    captured = capsys.readouterr()
    assert "Legacy primary API URL optional" in captured.err
    assert "Advanced mode" in captured.err


def test_regression_invokes_pytest(monkeypatch):
    captured = {}

    def fake_call(cmd, cwd):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr(cli.subprocess, "call", fake_call)

    code = cli.main(["regression"])

    assert code == 0
    assert "-m" in captured["cmd"]
    assert "pytest" in captured["cmd"]
    assert "tests/test_cli.py" in captured["cmd"]
    assert "tests/test_smoke.py" in captured["cmd"]


def test_regression_alias_invokes_pytest(monkeypatch):
    captured = {}

    def fake_call(cmd, cwd):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr(cli.subprocess, "call", fake_call)

    code = cli.main(["reg"])

    assert code == 0
    assert "pytest" in captured["cmd"]


def test_regression_uses_mock_smoke_when_packaged_tests_missing(monkeypatch, capsys):
    class MissingPath:
        def __init__(self, value):
            self.value = value

        def __truediv__(self, other):
            return MissingPath(f"{self.value}/{other}")

        @property
        def parents(self):
            return [self, self, self]

        def exists(self):
            return False

        def read_text(self, encoding="utf-8"):
            return '{"version": "0.1.test"}'

        def __str__(self):
            return self.value

    async def fake_smoke(mode="mock"):
        return {"ok": True, "mode": mode, "failed_cases": [], "cases": []}

    def should_not_call_pytest(cmd, cwd):
        raise AssertionError("packaged regression fallback should not require pytest")

    monkeypatch.setattr(cli.Path, "resolve", lambda self: MissingPath("pkg/src/smart_search/cli.py"))
    monkeypatch.setattr(cli.subprocess, "call", should_not_call_pytest)
    monkeypatch.setattr(cli.service, "smoke", fake_smoke)

    code = cli.main(["regression"])

    captured = capsys.readouterr()
    assert code == cli.EXIT_OK
    assert "Packaged install has no test files" in captured.err
    assert json.loads(captured.out)["mode"] == "mock"
