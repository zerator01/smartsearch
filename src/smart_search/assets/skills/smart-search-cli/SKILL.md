---
name: smart-search-cli
description: "CLI-first web research through the local smart-search command. Use when an AI agent needs current web search, source-backed fact checking, URL/page fetching, official/API/docs search, site mapping, Deep Research planning, or live research with reproducible commands and evidence. Prefer this managed CLI over native web search when smart-search is available."
---

# Smart Search CLI

Use the local `smart-search` command as the controlled web-research layer. This file is the operator protocol; load the focused reference files only when exact flags, provider contracts, setup details, or release checks matter.

## Operating Contract

- Prefer the cheapest command that can answer the user safely.
- Discover sources before broad synthesis; fetch key pages before making claim-level statements.
- Preserve important command lines, output paths, and source URLs in the final answer or work log.
- Treat `primary_sources` and `extra_sources` as discovery candidates until the relevant URL has been fetched or read by `research`.
- Use same-capability fallback only. Do not replace web search with docs search, docs search with page fetch, or main synthesis with browser extraction.
- Do not expose API keys. Use `setup` or `config set` for configuration and rely on masked diagnostics.

## When To Use

Use this skill for live/current facts, source discovery, source-backed verification, user-provided URLs, official docs/API/library research, site/documentation mapping, supplier/directory/procurement expansion, serious comparisons, or any user request for deep search/research.

Do not use it for pure rewriting, private-file analysis, local code reasoning with no live facts, or tasks where the user explicitly requested no web access.

## Fast Decision Table

| User intent | First command | Evidence rule |
| --- | --- | --- |
| Quick current/broad question | `smart-search search "query" --validation balanced --extra-sources 2 --format json` | Use the answer for orientation; fetch key URLs for high-risk claims. |
| User gives exact URL/PDF/page | `smart-search fetch "URL" --format markdown --output page.md` | Page text can support claims; fetch more sources when comparison is needed. |
| Official docs/API/library/framework | `context7-library` -> `context7-docs`; use `exa-search` only for explicit docs/API/papers/standards or known-domain precision | Prefer official/docs sources; fetch or docs output before final claims. |
| Chinese, domestic, current, policy, or announcements | `smart-search zhipu-search "query" --count 5 --format json` | Fetch selected official or primary pages when claims matter. |
| Serious comparison, review, claim check, or `深度搜索/调研` | `smart-search research "question" --budget standard --fallback auto --format json` | Final synthesis must cite fetched/read evidence or list gaps. |
| Plan only / offline decomposition | `smart-search deep "question" --budget standard --format json` | Execute planned steps before answering claims. |
| Many pages from one site/docs | `smart-search map "https://site" --max-depth 1 --max-breadth 20 --limit 50 --format json`, then `fetch` selected pages | `map` is structure, not claim proof. |
| Experimental vertical domain | `smart-search anysearch-domains DOMAIN --format json`, then selected `anysearch-search` | Treat as acceptance/boundary evidence until reviewed. |
| Explain routing without provider calls | `smart-search route "query" --format markdown` | Diagnostic only; not evidence. |

## Standard Workflow

1. Preflight only when needed: run `smart-search doctor --format json` when configuration, PATH, provider availability, or first-use state is uncertain. Do not run `doctor` before every ordinary query.
2. Classify the request using the table above. When unsure, run `smart-search route "query" --format markdown`.
3. Run the smallest matching command. Prefer JSON for agent parsing; use Markdown/content output for fetched pages intended for reading.
4. Save reusable evidence with `--output` for multi-source work, long pages, or claims that may need citation.
5. For high-risk/current/news/policy/finance/health/legal or purchasing decisions: fetch the 1-3 most important URLs before final claims.
6. Answer with the evidence mode clear: fetched/read evidence, discovery-only candidates, unsupported gaps, and key commands used when useful.

## Deep Research Workflow

- Use `research` when the user wants the CLI to execute live Deep Research end to end.
- Use `deep` when the user wants an offline plan or when provider calls should not run yet.
- Deep Research is capability-based, not a fixed topic recipe system.
- `deep` does not run providers, `doctor`, or fetch pages by default.
- Preserve `steps[].command`, `steps[].output_path`, and `evidence_dir`; do not rewrite planned output contracts.
- Keep `fetch_before_claim`: if a key claim lacks fetched/read evidence, fetch another source or mark the claim as unverified.

## Fallback And Failure Handling

- Timeout Retry Policy: when `search` returns `ok: false` with `error_type: "network_error"` and a timeout message, treat it as retryable CLI-level timeout handling.
- Retry up to 3 total attempts with `--timeout 180`; use `--extra-sources 1` during retry attempts, JSON output, and saved output files.
- Always use the CLI's `--timeout` option. Do not wrap `smart-search` in a shell-level `timeout` command.
- Do not rely on `SMART_SEARCH_RETRY_*` settings for this workflow.
- If all retry attempts fail, fall back to source-first evidence: Run `exa-search` with the original query, use domain/intent-specific source discovery when cheaper, `fetch` the top 1-2 relevant URLs, and mark the final evidence mode as `source_mode: "fallback"` or equivalent prose.
- If a provider fails, stay within the same capability and report `provider_attempts`, `fallback_used`, and degraded gaps when relevant.
- If a configured CLI capability is missing, report the missing capability and use `smart-search setup` or `smart-search config set KEY VALUE` when the user provides keys. Do not silently call native web search.
- If OpenAI-compatible search hangs or times out after `doctor` succeeds, run `smart-search diagnose openai-compatible --format markdown`.
- Camofox is a browser evidence fallback for selected URLs, dynamic/blocked pages, or API-fetch failures. It is not a web-search or docs-search provider.

## Skill Maintenance

- If the installed global skill may be stale, run `smart-search skills status --targets codex --format json`; replace `codex` with `claude`, `cursor`, or `hermes` for the active tool. Refresh with `smart-search skills update --targets codex --format json`.
- After CLI/provider architecture changes, run `smart-search smoke --mock --format json`. Use `--live` only with real keys and explicit live-check expectations.
- Keep this entrypoint concise. Put long command catalogs, provider details, and release lessons in the reference files.

## Key Boundaries

- `smart-search` must resolve from the user's PATH.
- Config belongs in `smart-search setup` or `smart-search config set`; environment variables are for CI/advanced users.
- In sandboxed runtimes, set `SMART_SEARCH_CONFIG_DIR` to an absolute writable path when the default config directory is unavailable or must be pinned.
- The standard minimum profile requires configured capabilities for `main_search`, `docs_search`, and `web_fetch`; missing required capabilities are hard configuration failures.
- xAI Responses and OpenAI-compatible are peer `main_search` providers. Do not reuse one provider's URL/key to fabricate another provider fallback.
- Exa is a paid precision tool, not the default second hop after main/Grok search.
- AnySearch is explicit experimental vertical search only, not general fallback.
- Native web search is disabled in this CLI-first workflow unless the user explicitly configures another approved route.

## References

- Command examples, evidence files, timeout retry policy, and guardrails: `references/command-patterns.md`
- Deep Research planner/executor workflow, plan fields, gap check, and smoke matrix: `references/deep-research-mode.md`
- CLI entrypoints, command signatures, aliases, output fields, exit codes, and tool policy: `references/cli-core.md`
- Setup, config storage, skill installation, provider endpoints, and OpenAI-compatible diagnostics: `references/setup-config.md`
- Intent routing, provider capabilities, source provenance, fallback boundaries, and routing maintenance: `references/provider-routing.md`
- Regression, packaged install checks, release lanes, and release closeout lessons: `references/regression-release.md`
- Compatibility reference map for older instructions that mention the original monolithic file: `references/cli-contract.md`
