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

# Unambiguous typographic normalisation only (applied to unit and evidence alike).
_TYPO = str.maketrans({
    "\u00a0": " ", "\u2009": " ", "\u202f": " ",
    "\u00b2": "2", "\u00b3": "3", "\u00b5": "\u03bc",
})
_DASHES = "-\u2010\u2011\u2012\u2013\u2014\u2212"
# A number token: digits with optional , or . groups, or a leading-dot decimal; optional exponent.
_NUM_RE = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)*|\.\d+)(?:[eE]([+\-\u2212]?\d+))?(?![\w])")


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
    pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(unit) + r"(?![A-Za-z0-9])")
    return [(m.start(), m.end()) for m in pat.finditer(evidence)]


def _as_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", _typo(s)).strip()


def _check_claim(cid: str, claim: dict[str, Any], sources: list[str] | None) -> tuple[dict, list[str], list[str]]:
    warns: list[str] = []
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
        warns.append(
            f"{cid}: 缺 evidence 且未标 {INFERRED_MARK}；请补原文引文，"
            f"或原文不足时在 evidence 写 {INFERRED_MARK} + 推断依据"
        )
        return status, warns, struct
    if ev.lstrip().startswith(INFERRED_MARK):
        status["value_unit"] = "inferred"
        status["evidence_source"] = "inferred"
        if not ev.lstrip()[len(INFERRED_MARK):].strip():
            warns.append(f"{cid}: 标了 {INFERRED_MARK} 但未写推断依据")
        return status, warns, struct

    ev_n = _typo(ev)
    if sources is not None:
        needle = _squash(ev)
        status["evidence_source"] = "found" if any(needle in s for s in sources) else "not_found"
        if status["evidence_source"] == "not_found":
            warns.append(f"{cid}: evidence 在知识库原文中未逐字找到；请回原文核对引文")

    if value is None or not unit:
        return status, warns, struct

    target = _as_decimal(value)
    nums = _numbers(ev_n)
    hits = [n for n in nums if n[0] == target]
    spans = _unit_spans(_typo(unit), ev_n)
    if not hits:
        status["value_unit"] = "value_not_found"
        warns.append(f"{cid}: value {value!r} 未在 evidence 中以相同数值/正负号出现；请回原文确认")
    elif not spans:
        status["value_unit"] = "unit_not_verbatim"
        warns.append(
            f"{cid}: unit {unit!r} 未在 evidence 中作为原文单位短语逐字出现"
            f"（整词边界）；请照抄引文中的单位短语，勿压成短符号"
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
            warns.append(f"{cid}: value 与 unit 在 evidence 中相距较远；请确认该数确属该单位")
    return status, warns, struct


def check_claims_payload(
    data: Any,
    *,
    sources: Iterable[str] | None = None,
    expected_count: int | None = None,
) -> dict[str, Any]:
    """Warn-only check. Returns status/warnings; never mutates ``data``.

    ``expected_count`` is the agent-declared N from the question-facing short
    checklist (never gold). When provided and claim count differs, warn only.
    When omitted/None, skip the count check and remind that N was not supplied.
    """
    src = [_squash(s) for s in sources] if sources is not None else None
    warnings: list[str] = []
    structural: list[str] = []
    per_claim: list[dict] = []

    if not isinstance(data, dict) or not isinstance(data.get("claims"), list):
        structural.append("claims.json 根应为 object 且含 claims 数组")
        return _result("checked", warnings, structural, per_claim, 0)

    claims = data["claims"]
    abstained = data.get("abstained")
    if abstained is not None and not isinstance(abstained, bool):
        structural.append("abstained 应为布尔值")
    if abstained is True and claims:
        structural.append("abstained=true 但 claims 非空；二者不一致")
    if not abstained and not claims:
        warnings.append("claims 为空且未 abstained；确认原文是否确无可答数字")

    # Count check: warn-only; N from question checklist only (never gold / hard gate).
    if expected_count is None:
        warnings.append(
            "未提供 expected_count（题面短清单 N）；跳过条数核对。"
            "调用时传入 expected_count=清单条数（可枚举时）。"
        )
    elif not isinstance(expected_count, int) or isinstance(expected_count, bool) or expected_count < 0:
        warnings.append(
            f"expected_count={expected_count!r} 非法（应为非负整数）；跳过条数核对"
        )
    elif abstained is True:
        # abstained empty set: count mismatch vs positive N is still useful signal
        if expected_count != 0 and len(claims) != expected_count:
            warnings.append(
                f"abstained=true 且 claims 条数 {len(claims)} ≠ 题面清单 N={expected_count}；"
                f"检查是否应交付非空 claims（勿按告警批量删条）"
            )
    elif len(claims) != expected_count:
        warnings.append(
            f"claims 条数 {len(claims)} ≠ 题面清单 N={expected_count}；"
            f"检查多报或漏报（勿按告警批量删条）"
        )

    for i, claim in enumerate(claims):
        where = f"claims[{i}]"
        if not isinstance(claim, dict):
            structural.append(f"{where}: 应为 object")
            continue
        cid = str(claim.get("claim_id") or where)
        st, w, s = _check_claim(cid, claim, src)
        per_claim.append(st)
        warnings.extend(w)
        structural.extend(s)
    return _result("checked", warnings, structural, per_claim, len(claims))


def _result(status: str, warnings: list[str], structural: list[str], per_claim: list[dict], n: int) -> dict[str, Any]:
    return {
        "status": status,  # checked = the check ran; it says nothing about correctness
        "warnings": warnings,
        "structural_warnings": structural,
        "claims": per_claim,
        "claim_count": n,
        "auto_deleted": False,
        "message": (
            "仅提醒，未改写 claims。告警不要求清零：逐条回原文确认后再决定是否修改；"
            "不要按告警批量删条。"
        ),
    }


def check_claims_file(
    path: Path,
    *,
    sources: Iterable[str] | None = None,
    expected_count: int | None = None,
) -> dict[str, Any]:
    """Load JSON at ``path`` and run :func:`check_claims_payload` (read-only)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _result("unavailable", [f"无法读取 {path}：{exc}"], [], [], 0)
    if not text.strip():
        return _result("unavailable", [f"{path} 为空"], [], [], 0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return _result("unavailable", [], [f"JSON 无法解析：{exc}"], [], 0)
    return check_claims_payload(data, sources=sources, expected_count=expected_count)
