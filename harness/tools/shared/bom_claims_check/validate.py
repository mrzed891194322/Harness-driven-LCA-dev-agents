"""Read-only BOM claims check (warn-only). Never deletes or rewrites claims.

Each numeric claim is compared with its own ``evidence`` quote:
- the unit string (source unit phrase) must occur in the evidence
  (case-sensitive, whole-token / word-boundary; not forced to short symbols);
- the value must occur as a number near that unit (exact, no float tolerance);
- optionally, the evidence quote is located in source texts.

Results are *status*, not correctness: ``checked`` means the check ran, not that
the claim is right. Does not apply the scorer synonym table or rewrite units.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

NEAR_CHARS = 40
# Evidence prefix marking a value the agent inferred/estimated because the source is insufficient.
INFERRED_MARK = "[推断]"  # max gap between a number and its unit inside one quote

# Stable warning codes for host/MCP classification (messages stay human-readable).
WARN_CHECKLIST_INVALID = "CHECKLIST_INVALID"
WARN_EXPECTED_COUNT_MISSING = "EXPECTED_COUNT_MISSING"
WARN_EXPECTED_COUNT_INVALID = "EXPECTED_COUNT_INVALID"
WARN_CLAIMS_COUNT_MISMATCH = "CLAIMS_COUNT_MISMATCH"
WARN_ABSTAIN_COUNT_MISMATCH = "ABSTAIN_COUNT_MISMATCH"
WARN_CHECKLIST_ITEM_UNCOVERED = "CHECKLIST_ITEM_UNCOVERED"
WARN_CLAIMS_UNMATCHED_CHECKLIST = "CLAIMS_UNMATCHED_CHECKLIST"
WARN_CLAIMS_EMPTY_NO_ABSTAIN = "CLAIMS_EMPTY_NO_ABSTAIN"
WARN_EVIDENCE_MISSING = "EVIDENCE_MISSING"
WARN_INFERRED_BASIS_MISSING = "INFERRED_BASIS_MISSING"
WARN_INFERRED_FORMULA_VALUE_MISSING = "INFERRED_FORMULA_VALUE_MISSING"
WARN_EVIDENCE_NOT_IN_SOURCE = "EVIDENCE_NOT_IN_SOURCE"
WARN_VALUE_NOT_IN_EVIDENCE = "VALUE_NOT_IN_EVIDENCE"
WARN_UNIT_NOT_VERBATIM = "UNIT_NOT_VERBATIM"
WARN_VALUE_UNIT_FAR_APART = "VALUE_UNIT_FAR_APART"

# Unambiguous typographic normalisation only (applied to unit and evidence alike).
_TYPO = str.maketrans({
    "\u00a0": " ", "\u2009": " ", "\u202f": " ",
    "\u00b2": "2", "\u00b3": "3", "\u00b5": "\u03bc",
})
_DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2212"
# A number token: digits with optional , or . groups, or a leading-dot decimal; optional exponent.
_NUM_RE = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)*|\.\d+)(?:[eE]([+\-\u2212]?\d+))?(?![0-9])")


def _typo(s: str) -> str:
    return s.translate(_TYPO)


def _token_values(tok: str, exp: str | None) -> set[Decimal]:
    """Candidate values for a number token (ambiguous separators -> several)."""
    cands: set[str] = set()
    if "," in tok and "." in tok:
        # whichever comes last is the decimal mark
        if tok.rfind(".") > tok.rfind(","):
            cands.add(tok.replace(",", ""))
        else:
            cands.add(tok.replace(".", "").replace(",", "."))
    elif "," in tok:
        parts = tok.split(",")
        if all(len(p) == 3 for p in parts[1:]):
            cands.add(tok.replace(",", ""))  # thousands grouping
        if len(parts) == 2:
            cands.add(tok.replace(",", "."))  # decimal comma
    elif tok.count(".") > 1:
        parts = tok.split(".")
        if all(len(p) == 3 for p in parts[1:]):
            cands.add(tok.replace(".", ""))
    else:
        cands.add(tok)
    out: set[Decimal] = set()
    for c in cands:
        if exp:
            c = f"{c}e{exp.replace(chr(0x2212), '-')}"
        try:
            out.add(Decimal(c))
        except InvalidOperation:
            continue
    return out


def _numbers(evidence: str) -> list[tuple[Decimal, int, int]]:
    """All signed numbers in ``evidence`` as (value, start, end).

    A dash directly before a number is a minus sign only when it does not follow
    another number (``2–5`` is a range: both endpoints positive).
    """
    found: list[tuple[Decimal, int, int]] = []
    for m in _NUM_RE.finditer(evidence):
        start = m.start()
        sign = 1
        j = start - 1
        if j >= 0 and evidence[j] in _DASHES:
            k = j - 1
            while k >= 0 and evidence[k] == " ":
                k -= 1
            is_range = k >= 0 and (evidence[k].isdigit() or evidence[k] == "%")
            if not is_range:
                sign = -1
                start = j
        for v in _token_values(m.group(1), m.group(2)):
            found.append((v * sign, start, m.end()))
    return found


def _unit_spans(unit: str, evidence: str) -> list[tuple[int, int]]:
    left = r"(?<![A-Za-z0-9])" if unit[:1].isdigit() else r"(?<![A-Za-z])"
    pat = re.compile(left + re.escape(unit) + r"(?![A-Za-z0-9])")
    return [(m.start(), m.end()) for m in pat.finditer(evidence)]


def _looks_like_formula(text: str) -> bool:
    if "=" in text and re.search(r"\d", text):
        return True
    if re.search(r"[\×*/]", text) and re.search(r"\d", text):
        return True
    return False


def _formula_mentions_value(value: Any, body: str) -> bool:
    target = _as_decimal(value)
    if target is None:
        return True
    for n in _numbers(_typo(body)):
        if n[0] == target:
            return True
    return False


def _as_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", _typo(s)).strip()


def _add_warn(
    warns: list[str],
    details: list[dict[str, str]],
    code: str,
    msg: str,
) -> None:
    warns.append(msg)
    details.append({"code": code, "msg": msg})


def _check_claim(cid: str, claim: dict[str, Any], sources: list[str] | None) -> tuple[dict, list[str], list[str], list[dict[str, str]]]:
    warns: list[str] = []
    warn_details: list[dict[str, str]] = []
    struct: list[str] = []
    value, unit, ev = claim.get("value"), claim.get("unit"), claim.get("evidence")
    status = {"claim_id": cid, "value_unit": "unavailable", "evidence_source": "unavailable"}

    if not claim.get("claim_id"):
        struct.append(f"{cid}: 缺 claim_id")
    if isinstance(value, bool):
        struct.append(f"{cid}: value 是布尔值，应为数字")
        value = None
    elif value is not None and not isinstance(value, (int, float)):
        struct.append(f"{cid}: value 不是数字（{type(value).__name__}）")
        value = None
    if unit is not None and not isinstance(unit, str):
        struct.append(f"{cid}: unit 不是字符串")
        unit = None
    if ev is not None and not isinstance(ev, str):
        struct.append(f"{cid}: evidence 不是字符串")
        ev = None
    if (claim.get("value") is None) != (claim.get("unit") is None):
        struct.append(f"{cid}: value 与 unit 应成对填写（一个为 null/缺失）")
    if claim.get("value") is None and claim.get("unit") is None and not (claim.get("text") or "").strip():
        struct.append(f"{cid}: 既无 value/unit 也无 text")

    if not ev or not ev.strip():
        _add_warn(
            warns,
            warn_details,
            WARN_EVIDENCE_MISSING,
            f"{cid}: 缺 evidence；请补原文引文（可清晰推导时简要说明依据）",
        )
        return status, warns, struct, warn_details
    if ev.lstrip().startswith(INFERRED_MARK):
        status["value_unit"] = "inferred"
        status["evidence_source"] = "inferred"
        body = ev.lstrip()[len(INFERRED_MARK):].strip()
        if not body:
            _add_warn(
                warns,
                warn_details,
                WARN_INFERRED_BASIS_MISSING,
                f"{cid}: 标了 {INFERRED_MARK} 但未写推断依据",
            )
        elif value is not None and _looks_like_formula(body) and not _formula_mentions_value(value, body):
            _add_warn(
                warns,
                warn_details,
                WARN_INFERRED_FORMULA_VALUE_MISSING,
                f"{cid}: [推断] 算式/依据中未出现与 value 相同的数值 {value!r}；请核对换算或算式",
            )
        return status, warns, struct, warn_details

    ev_n = _typo(ev)
    if sources is not None:
        needle = _squash(ev)
        status["evidence_source"] = "found" if any(needle in s for s in sources) else "not_found"
        if status["evidence_source"] == "not_found":
            _add_warn(
                warns,
                warn_details,
                WARN_EVIDENCE_NOT_IN_SOURCE,
                f"{cid}: evidence 在知识库原文中未逐字找到；请回原文核对引文",
            )

    if value is None or not unit:
        return status, warns, struct, warn_details

    target = _as_decimal(value)
    nums = _numbers(ev_n)
    hits = [n for n in nums if n[0] == target]
    spans = _unit_spans(_typo(unit), ev_n)
    if not hits:
        status["value_unit"] = "value_not_found"
        _add_warn(
            warns,
            warn_details,
            WARN_VALUE_NOT_IN_EVIDENCE,
            f"{cid}: value {value!r} 未在 evidence 中以相同数值/正负号出现；请回原文确认",
        )
    elif not spans:
        status["value_unit"] = "unit_not_verbatim"
        _add_warn(
            warns,
            warn_details,
            WARN_UNIT_NOT_VERBATIM,
            f"{cid}: unit {unit!r} 未在 evidence 中出现（整词边界）；请核对 unit 是否与引文一致",
        )
    else:
        all_spans = [(s, e) for (_, s, e) in nums]

        def _clear(a: int, b: int) -> bool:  # no other number strictly between a and b
            return not any(a <= s and e <= b for (s, e) in all_spans)

        near = any(
            (0 <= us - ne <= NEAR_CHARS and _clear(ne, us))
            or (0 <= ns - ue <= NEAR_CHARS and _clear(ue, ns))
            for (_, ns, ne) in hits for (us, ue) in spans
        )
        status["value_unit"] = "near" if near else "far_apart"
        if not near:
            _add_warn(
                warns,
                warn_details,
                WARN_VALUE_UNIT_FAR_APART,
                f"{cid}: value 与 unit 在 evidence 中相距较远；请确认该数确属该单位",
            )
    return status, warns, struct, warn_details


def check_claims_payload(
    data: Any,
    *,
    sources: Iterable[str] | None = None,
    expected_count: int | None = None,
    checklist: list[str] | None = None,
) -> dict[str, Any]:
    """Warn-only check. Returns status/warnings; never mutates ``data``.

    ``checklist`` is the model-written question list (object × value asked);
    when given, N = len(checklist) and overrides ``expected_count``.

    ``expected_count`` is the agent-declared N from the question-facing short
    checklist (never gold). When provided and claim count differs, warn only.
    When omitted/None, skip the count check and remind that N was not supplied.
    """
    src = [_squash(s) for s in sources] if sources is not None else None
    warnings: list[str] = []
    warning_details: list[dict[str, str]] = []
    structural: list[str] = []
    per_claim: list[dict] = []

    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        structural.append("claims.json 根应为 object 且含 claims 数组")
        return _result("checked", warnings, warning_details, structural, per_claim, 0)

    claims = data["claims"]
    abstained = data.get("abstained")
    if abstained is not None and not isinstance(abstained, bool):
        structural.append("abstained 应为布尔值")
    if abstained is True and claims:
        structural.append("abstained=true 但 claims 非空；二者不一致")
    # Empty claims without abstained is valid (PCFBench: no abstain protocol).

    checklist_items: list[str] | None = None
    if checklist is not None:
        if isinstance(checklist, list) and all(isinstance(x, str) and x.strip() for x in checklist):
            checklist_items = [x.strip() for x in checklist]
            expected_count = len(checklist_items)
        else:
            _add_warn(
                warnings,
                warning_details,
                WARN_CHECKLIST_INVALID,
                "checklist 应为非空字符串数组（每项=题面所问 对象×指标）；已忽略",
            )

    # Count check: warn-only; N from question checklist only (never gold / hard gate).
    if expected_count is None:
        _add_warn(
            warnings,
            warning_details,
            WARN_EXPECTED_COUNT_MISSING,
            "未提供 checklist/expected_count（题面短清单 N）；跳过条数核对。"
            "调用时传入 checklist=[题面所问 对象×指标, ...]（可枚举时）。",
        )
    elif not isinstance(expected_count, int) or isinstance(expected_count, bool) or expected_count < 0:
        _add_warn(
            warnings,
            warning_details,
            WARN_EXPECTED_COUNT_INVALID,
            f"expected_count={expected_count!r} 非法（应为非负整数）；跳过条数核对",
        )
    elif abstained is True:
        if expected_count != 0 and len(claims) != expected_count:
            _add_warn(
                warnings,
                warning_details,
                WARN_ABSTAIN_COUNT_MISMATCH,
                f"abstained=true 且 claims 条数 {len(claims)} ≠ 题面清单 N={expected_count}；"
                f"检查是否应交付非空 claims",
            )
    elif len(claims) != expected_count:
        _add_warn(
            warnings,
            warning_details,
            WARN_CLAIMS_COUNT_MISMATCH,
            f"claims 条数 {len(claims)} ≠ 题面清单 N={expected_count}：请逐条说明其对应的清单项",
        )
        if checklist_items is not None:
            for w, d in _coverage_hints(checklist_items, claims):
                warnings.append(w)
                warning_details.append(d)

    for i, claim in enumerate(claims):
        where = f"claims[{i}]"
        if not isinstance(claim, dict):
            structural.append(f"{where}: 应为 object")
            continue
        cid = str(claim.get("claim_id") or where)
        st, w, s, wd = _check_claim(cid, claim, src)
        per_claim.append(st)
        warnings.extend(w)
        warning_details.extend(wd)
        structural.extend(s)
    return _result("checked", warnings, warning_details, structural, per_claim, len(claims))


_TOKEN_RE = re.compile("[A-Za-z0-9]+|[\u4e00-\u9fff]+")


def _tokens(s: str) -> set[str]:
    """Alnum / CJK runs longer than 1 char (for checklist↔claim matching)."""
    return {t.lower() for t in _TOKEN_RE.findall(s) if len(t) > 1}


def _label_matches_item(label: str, item_key: str) -> bool:
    """True if label covers checklist item via substring either way or meaningful token overlap.

    Meaningful = smaller token set is mostly covered; a single shared token only
    counts when the smaller side itself has just one token (avoids ``mass`` alone
    linking unrelated ``steel frame mass`` ↔ ``glass mass``).
    """
    if not label or not item_key:
        return False
    if item_key in label or label in item_key:
        return True
    lt, it = _tokens(label), _tokens(item_key)
    if not lt or not it:
        return False
    smaller, larger = (it, lt) if len(it) <= len(lt) else (lt, it)
    overlap = smaller & larger
    if not overlap:
        return False
    need = max(1, (len(smaller) + 1) // 2)
    if len(overlap) < need:
        return False
    return len(overlap) >= 2 or len(smaller) == 1


def _claim_label(claim: Any) -> str:
    """Join legal schema fields only (item_id/field/text/claim_id); never object/item/name."""
    if not isinstance(claim, dict):
        return ""
    parts = [claim.get(k) for k in ("item_id", "field", "text", "claim_id")]
    return _squash(" ".join(str(p) for p in parts if isinstance(p, str))).lower()


def _coverage_hints(items: list[str], claims: list[Any]) -> list[tuple[str, dict[str, str]]]:
    """Best-effort missing/extra hints by token/substring match (hint only)."""
    labels = [_claim_label(c) for c in claims]
    keys = [_squash(i).lower() for i in items]
    out: list[tuple[str, dict[str, str]]] = []
    if len(claims) < len(items):
        missing = [
            i for i, k in zip(items, keys)
            if not any(_label_matches_item(lb, k) for lb in labels)
        ]
        if missing and len(missing) < len(items):
            msg = f"清单项可能无对应 claim：{missing}"
            out.append((msg, {"code": WARN_CHECKLIST_ITEM_UNCOVERED, "msg": msg}))
    elif len(claims) > len(items):
        extra = [
            str(c.get("claim_id") or f"claims[{n}]")
            for n, (c, lb) in enumerate(zip(claims, labels))
            if isinstance(c, dict) and lb and not any(_label_matches_item(lb, k) for k in keys)
        ]
        if extra and len(extra) < len(claims):
            msg = f"这些 claim 未匹配任何清单项（可能多报）：{extra}"
            out.append((msg, {"code": WARN_CLAIMS_UNMATCHED_CHECKLIST, "msg": msg}))
    return out


def _result(
    status: str,
    warnings: list[str],
    warning_details: list[dict[str, str]],
    structural: list[str],
    per_claim: list[dict],
    n: int,
) -> dict[str, Any]:
    codes = [d["code"] for d in warning_details if isinstance(d.get("code"), str)]
    return {
        "status": status,
        "warnings": warnings,
        "warning_details": warning_details,
        "warning_codes": codes,
        "structural_warnings": structural,
        "claims": per_claim,
        "claim_count": n,
        "auto_deleted": False,
        "message": (
            "仅提醒，未改写 claims。请按告警逐条对照题面清单处置后再核。"
        ),
    }


def check_claims_file(
    path: Path,
    *,
    sources: Iterable[str] | None = None,
    expected_count: int | None = None,
    checklist: list[str] | None = None,
) -> dict[str, Any]:
    """Load JSON at ``path`` and run :func:`check_claims_payload` (read-only)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _result("unavailable", [f"无法读取 {path}：{exc}"], [], [], [], 0)
    if not text.strip():
        return _result("unavailable", [f"{path} 为空"], [], [], [], 0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return _result("unavailable", [], [], [f"JSON 无法解析：{exc}"], [], 0)
    return check_claims_payload(data, sources=sources, expected_count=expected_count, checklist=checklist)
