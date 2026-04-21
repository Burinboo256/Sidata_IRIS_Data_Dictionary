"""
ai_provider.py — AI provider abstraction for IRIS SQL query generation.

Supported providers:
  - Claude (Anthropic)
  - OpenRouter
  - OpenAI / Codex
  - Typhoon (SCB Thai LLM)
  - Ollama (local)
  - Custom Endpoint (OpenAI-compatible)
"""
import re
import requests

# ─── Provider registry ────────────────────────────────────────────────────────

PROVIDERS: dict = {
    "Claude (Anthropic)": {
        "type": "claude",
        "base_url": "https://api.anthropic.com",
        "needs_key": True,
        "default_model": "claude-sonnet-4-6",
        "models": [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
        ],
        "key_hint": "sk-ant-...",
        "docs_url": "https://console.anthropic.com/",
    },
    "OpenRouter": {
        "type": "openai_compat",
        "base_url": "https://openrouter.ai/api/v1",
        "needs_key": True,
        "default_model": "anthropic/claude-3.5-sonnet",
        "models": [
            "anthropic/claude-3.5-sonnet",
            "anthropic/claude-3-haiku",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-chat",
            "google/gemini-2.0-flash-001",
            "mistralai/mistral-large",
        ],
        "key_hint": "sk-or-...",
        "docs_url": "https://openrouter.ai/keys",
    },
    "OpenAI / Codex": {
        "type": "openai_compat",
        "base_url": "https://api.openai.com/v1",
        "needs_key": True,
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-mini", "o3-mini"],
        "key_hint": "sk-...",
        "docs_url": "https://platform.openai.com/api-keys",
    },
    "Typhoon (SCB Thai)": {
        "type": "openai_compat",
        "base_url": "https://api.opentyphoon.ai/v1",
        "needs_key": True,
        "default_model": "typhoon-v2-70b-instruct",
        "models": [
            "typhoon-v2-70b-instruct",
            "typhoon-v2-8b-instruct",
            "typhoon-v2-r1-70b-instruct",
        ],
        "key_hint": "sk-...",
        "docs_url": "https://opentyphoon.ai/",
    },
    "Ollama (Local)": {
        "type": "ollama",
        "base_url": "http://localhost:11434",
        "needs_key": False,
        "default_model": "llama3.2",
        "models": [],  # fetched dynamically via get_ollama_models()
        "key_hint": "",
        "docs_url": "https://ollama.ai/",
    },
    "Custom Endpoint": {
        "type": "openai_compat",
        "base_url": "",
        "needs_key": False,
        "default_model": "",
        "models": [],
        "key_hint": "optional",
        "docs_url": "",
    },
}

PROVIDER_NAMES: list = list(PROVIDERS.keys())


# ─── Ollama model discovery ────────────────────────────────────────────────────

def get_ollama_models(base_url: str = "http://localhost:11434") -> list:
    """Fetch available model names from a local Ollama instance."""
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


# ─── LLM call (unified entry point) ──────────────────────────────────────────

def call_llm(
    provider_name: str,
    model: str,
    api_key: str,
    base_url: str,
    messages: list,
    timeout: int = 120,
) -> str:
    """
    Send *messages* to the selected provider and return the assistant reply.

    *messages* is a standard OpenAI-style list:
        [{"role": "system"|"user"|"assistant", "content": "..."}]

    Raises RuntimeError with a human-readable description on any API error.
    """
    prov  = PROVIDERS.get(provider_name, {})
    ptype = prov.get("type", "openai_compat")
    url   = (base_url or prov.get("base_url", "")).rstrip("/")

    if ptype == "claude":
        return _call_claude(url, api_key, model, messages, timeout)
    if ptype == "ollama":
        return _call_ollama(url, model, messages, timeout)
    return _call_openai_compat(url, api_key, model, messages, timeout)


# ── Provider-specific implementations ─────────────────────────────────────────

def _call_claude(base_url: str, api_key: str, model: str, messages: list, timeout: int) -> str:
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    chat_msgs    = [m for m in messages if m["role"] != "system"]
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload: dict = {
        "model": model,
        "max_tokens": 4096,
        "messages": chat_msgs,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    r = requests.post(f"{base_url}/v1/messages", headers=headers, json=payload, timeout=timeout)
    _raise_for_status(r)
    return r.json()["content"][0]["text"]


def _call_openai_compat(base_url: str, api_key: str, model: str, messages: list, timeout: int) -> str:
    headers: dict = {"content-type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {"model": model, "messages": messages, "max_tokens": 4096}
    r = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=timeout)
    _raise_for_status(r)
    return r.json()["choices"][0]["message"]["content"]


def _call_ollama(base_url: str, model: str, messages: list, timeout: int) -> str:
    payload = {"model": model, "messages": messages, "stream": False}
    r = requests.post(
        f"{base_url}/api/chat",
        headers={"content-type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    _raise_for_status(r)
    return r.json()["message"]["content"]


def _raise_for_status(r: requests.Response) -> None:
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text[:400]
        raise RuntimeError(f"API error {r.status_code}: {detail}")


# ─── Connection test ──────────────────────────────────────────────────────────

def test_connection(
    provider_name: str,
    model: str,
    api_key: str,
    base_url: str,
    timeout: int = 15,
) -> tuple:
    """
    Send a minimal ping to the provider.
    Returns (success: bool, message: str).
    """
    ping = [{"role": "user", "content": "Reply with exactly the word OK and nothing else."}]
    try:
        reply = call_llm(provider_name, model, api_key, base_url, ping, timeout=timeout)
        preview = reply.strip()[:120]
        return True, f"Connected — model replied: _{preview}_"
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"


# ─── Schema context builder ───────────────────────────────────────────────────

def _score_table(row, keywords: list) -> int:
    """Keyword-relevance score for one table row."""
    name = str(row.get("sql_table_name", "")).lower()
    desc = str(row.get("class_description", "")).lower()
    mod  = str(row.get("module_name", "")).lower()
    score = 0
    for kw in keywords:
        if kw in name: score += 3
        if kw in desc: score += 2
        if kw in mod:  score += 1
    return score


def build_schema_context(
    query: str,
    tables_df,
    fields_df,
    fk_df,
    max_tables: int = 8,
) -> str:
    """
    Build a concise schema description for the given free-text *query*.
    Returns Markdown text suitable for inclusion in an LLM system prompt.
    """
    keywords = [w.lower() for w in re.findall(r"[a-zA-Zก-๙]{3,}", query)]

    scores    = tables_df.apply(lambda r: _score_table(r, keywords), axis=1)
    top_idx   = scores.nlargest(max_tables).index
    selected  = tables_df.loc[top_idx]
    if selected.empty:
        selected = tables_df.head(max_tables)

    resolved_fk = (
        fk_df[fk_df["resolve_status"] == "resolved"]
        if not fk_df.empty and "resolve_status" in fk_df.columns
        else fk_df
    )

    lines: list = []
    for _, tbl in selected.iterrows():
        sql_name   = tbl.get("sql_table_name", "")
        class_name = tbl.get("class_name", "")
        mod        = tbl.get("module_name", "")
        desc       = str(tbl.get("class_description", ""))

        lines.append(f"### {sql_name}")
        if desc and desc not in ("nan", ""):
            lines.append(f"*{desc}*")
        lines.append(f"Module: {mod} | Class: {class_name}")

        # Fields
        tbl_fields = (
            fields_df[fields_df["class_name"] == class_name]
            .sort_values("member_order")
            if "member_order" in fields_df.columns
            else fields_df[fields_df["class_name"] == class_name]
        )
        cap = 25
        for _, f in tbl_fields.head(cap).iterrows():
            fname = f.get("sql_field_name", "")
            ftype = f.get("member_type", "")
            fdesc = str(f.get("description", ""))
            row = f"  - `{fname}` ({ftype})"
            if fdesc and fdesc not in ("nan", ""):
                row += f" — {fdesc}"
            lines.append(row)
        if len(tbl_fields) > cap:
            lines.append(f"  - ... +{len(tbl_fields) - cap} more fields")

        # Outgoing FK relationships
        if not resolved_fk.empty and "source_sql_table_name" in resolved_fk.columns:
            out_fk = resolved_fk[resolved_fk["source_sql_table_name"] == sql_name]
            for _, fk_row in out_fk.iterrows():
                tgt  = fk_row.get("target_sql_table_name", "")
                srcf = fk_row.get("source_sql_field_name", "")
                lines.append(f"  → FK: `{srcf}` → `{tgt}`")

        lines.append("")

    return "\n".join(lines)


# ─── System-prompt builder ────────────────────────────────────────────────────

_IRIS_SYNTAX_NOTES = """\
**IRIS SQL Syntax:**
- `TOP N` not `LIMIT N`  (e.g. `SELECT TOP 10 * FROM ...`)
- Object-reference traversal: `field->RelatedField`  (e.g. `Admission->Patient->Name`)
- Display-value column: append `_DR`  (e.g. `AdmissionStatus_DR`)
- Text search: `field %STARTSWITH 'val'` or `field %CONTAINS 'val'`
- Date literal: `{d '2024-01-01'}`, today: `CURRENT_DATE`
- Class name → SQL table: `Module.ClassName` becomes `Module_ClassName`
- Always quote identifiers that clash with reserved words with double-quotes\
"""

_USE_CASE_SYSTEM: dict = {
    "business": """\
You are an expert InterSystems IRIS SQL developer at Siriraj Hospital.
Write precise, well-commented SQL to answer hospital business/operational questions.
Use clinical terminology (admission, ward, encounter, discharge, diagnosis, etc.).

{iris_syntax}

Response structure:
1. Briefly restate the question and list any assumptions
2. SQL query in a ```sql block
3. Short explanation of key clauses
4. End with exactly 3 actionable follow-up questions under the heading **## Suggested Follow-ups**\
""",

    "migration": """\
You are a database migration architect helping map legacy hospital schemas to InterSystems IRIS.
Produce IRIS-compatible DDL, mapping queries, and validation checks.

{iris_syntax}

Response structure:
1. Analyse the source schema or question
2. IRIS-equivalent DDL / mapping SQL in a ```sql block
3. Key differences: data types, constraints, indexing
4. Data-validation queries to run post-migration
5. End with 3 recommended next migration steps under **## Suggested Follow-ups**\
""",

    "interface": """\
You are an integration engineer expert in HL7 v2, FHIR R4, OMOP CDM v5, and InterSystems IRIS.
Generate source SQL queries and field-level mapping tables for the requested integration standard.

{iris_syntax}

Response structure:
1. Identify the target standard (HL7/FHIR/OMOP/cohort) and relevant segment/resource/table
2. Source SQL query in a ```sql block
3. Field mapping table (IRIS field → standard field)
4. Data quality / cardinality notes
5. End with 3 related integration tasks under **## Suggested Follow-ups**\
""",
}


def build_system_prompt(use_case: str, schema_context: str) -> str:
    """Compose the system prompt for the given *use_case* and pre-built *schema_context*."""
    template = _USE_CASE_SYSTEM.get(use_case, _USE_CASE_SYSTEM["business"])
    prompt   = template.format(iris_syntax=_IRIS_SYNTAX_NOTES)
    if schema_context.strip():
        prompt += f"\n\n**Relevant Schema (auto-selected):**\n{schema_context}"
    return prompt


# ─── Starter / follow-up prompts ─────────────────────────────────────────────

STARTER_PROMPTS: dict = {
    "business": [
        "แสดงจำนวน Cancel Admission แต่ละวันในช่วง 30 วันที่ผ่านมา",
        "นับผู้ป่วยที่ admit ในแต่ละ ward เดือนนี้",
        "หา Top 10 diagnosis ที่พบบ่อยที่สุดในปีนี้",
        "ค่าเฉลี่ย LOS (ระยะเวลานอน) แยกตาม ward",
        "จำนวน re-admission ภายใน 30 วันหลัง discharge",
        "รายชื่อ patient ที่มีนัดวันนี้แต่ยังไม่ check-in",
    ],
    "migration": [
        "Map legacy ADT table to IRIS Admission schema",
        "Generate CREATE TABLE DDL สำหรับ Patient ใน IRIS",
        "Validation query เพื่อตรวจสอบ record count หลัง migration",
        "แปลง stored procedure จาก SQL Server มาเป็น IRIS SQL",
        "Map ICD-9 diagnosis codes to ICD-10 in IRIS",
        "สร้าง index strategy สำหรับ IRIS table ที่ query บ่อย",
    ],
    "interface": [
        "Generate HL7 ADT^A01 query จาก IRIS admission data",
        "Map IRIS Patient fields to FHIR R4 Patient resource",
        "สร้าง OMOP CDM person table mapping จาก IRIS",
        "Build cohort SQL: DM type 2 patients admitted last year",
        "Generate HL7 ORU^R01 from IRIS lab result data",
        "Map IRIS encounter to OMOP visit_occurrence",
    ],
}


def parse_suggested_followups(response_text: str) -> list:
    """
    Extract the 3 follow-up suggestions the model appends under
    '## Suggested Follow-ups'.  Returns up to 3 strings.
    """
    followups: list = []
    in_section = False
    for line in response_text.split("\n"):
        if re.search(r"##\s*Suggested Follow", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            m = re.match(r"^[-*\d.]+\s+(.+)", line.strip())
            if m:
                followups.append(m.group(1).strip())
    return followups[:3]
