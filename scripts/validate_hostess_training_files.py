import json
import os
from typing import Dict, List, Tuple


def _detect_lang_simple(text: str) -> str:
    for ch in (text or ""):
        if "\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F" or "\u08A0" <= ch <= "\u08FF":
            return "ar"
    return "en"


def _norm_for_compare(text: str, lang: str) -> str:
    t = (text or "").strip().lower()
    if not t:
        return ""
    for ch in ["\u200f", "\u200e", "\u202a", "\u202b", "\u202c", "\ufeff"]:
        t = t.replace(ch, "")
    for ch in [".", ",", "!", "?", "؟", ":", ";", "،", "…", "-", "—", "(", ")", "[", "]", "{", "}", "\"", "'"]:
        t = t.replace(ch, " ")
    t = " ".join(t.split())
    return t


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_training_examples(path: str) -> Tuple[int, int]:
    data = _load_json(path)
    if not isinstance(data, list):
        raise RuntimeError(f"{path}: expected list")
    if len(data) % 2 != 0:
        raise RuntimeError(f"{path}: expected even length user/assistant pairs")

    seen: Dict[str, str] = {}
    duplicates = 0
    pairs = 0
    i = 0
    while i < len(data) - 1:
        u = data[i]
        a = data[i + 1]
        i += 2
        if not isinstance(u, dict) or not isinstance(a, dict):
            raise RuntimeError(f"{path}: expected dict items")
        if u.get("role") != "user" or a.get("role") != "assistant":
            raise RuntimeError(f"{path}: expected user/assistant alternating roles")
        q = (u.get("content") or "").strip()
        ans = (a.get("content") or "").strip()
        if not q or not ans:
            raise RuntimeError(f"{path}: empty content in a pair")
        lang = _detect_lang_simple(q + " " + ans)
        key = _norm_for_compare(q, lang)
        if key in seen:
            duplicates += 1
        else:
            seen[key] = q
        pairs += 1

    return pairs, duplicates


def main() -> None:
    base_dir = os.path.join("data", "training", "hostesses")
    total_pairs = 0
    total_dups = 0
    bad = []

    for root, _dirs, files in os.walk(base_dir):
        for fn in files:
            if fn != "training_examples.json":
                continue
            path = os.path.join(root, fn)
            try:
                pairs, dups = validate_training_examples(path)
                total_pairs += pairs
                total_dups += dups
                if dups:
                    bad.append((path, pairs, dups))
            except Exception as e:
                raise RuntimeError(str(e)) from e

    if bad:
        lines: List[str] = []
        for p, pairs, dups in bad:
            lines.append(f"{p}: {dups} duplicate questions within {pairs} pairs")
        raise SystemExit("\n".join(lines))

    print(f"OK: {total_pairs} pairs across {base_dir}, duplicates=0")


if __name__ == "__main__":
    main()
