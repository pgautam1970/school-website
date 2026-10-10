"""Stage 5 — Deduplication & cross-source matching.

Repeated announcements (same exam notice posted in teacher group, class groups
and the Facebook page) are clustered into consolidated findings while ALL
source references are retained. Clustering is deliberately conservative:
only near-identical normalized text on the same calendar day merges — similar
keywords alone never merge unrelated messages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

_TOKEN = re.compile(r"[^\s\.\,\!\?\;\:\(\)]+")
_STOP = {"the", "a", "an", "is", "are", "was", "of", "to", "in", "on", "for", "and", "or",
         "please", "plz", "will", "be", "that", "this", "it", "ho", "cha", "ko", "le", "ma"}


def _token_set(normalized: str) -> frozenset[str]:
    toks = _TOKEN.findall(normalized or "")
    return frozenset(t for t in toks if t not in _STOP and len(t) > 1)


def jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class EvidenceRef:
    platform: str            # whatsapp | facebook
    source_name: str         # group / page name
    ts: datetime | None
    sender: str
    excerpt: str
    ref_id: str = ""         # message id / permalink


@dataclass
class Cluster:
    primary_text: str
    evidence: list[EvidenceRef] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    priority: str = "LOW"
    priority_reason: str = ""
    confidence: float = 0.5
    status: str = "verified"   # verified (>=1 real source) | inferred | unresolved

    @property
    def source_count(self) -> int:
        return len(self.evidence)


def cluster_items(items: list[dict], threshold: float = 0.72,
                  min_tokens: int = 5) -> list[Cluster]:
    """items: {text_normalized, platform, source_name, ts, sender, categories,
    priority, priority_reason, confidence, ref_id, excerpt}"""
    clusters: list[Cluster] = []
    tok_cache: list[frozenset] = []

    for item in items:
        toks = _token_set(item["text_normalized"])
        merged = False
        if len(toks) >= min_tokens:
            for idx, cl in enumerate(clusters):
                # same day only — avoids merging recurring but unrelated notices
                if item["ts"] and cl.evidence and cl.evidence[0].ts:
                    if item["ts"].date() != cl.evidence[0].ts.date():
                        continue
                if jaccard(toks, tok_cache[idx]) >= threshold:
                    cl.evidence.append(EvidenceRef(
                        platform=item["platform"], source_name=item["source_name"],
                        ts=item.get("ts"), sender=item.get("sender", ""),
                        excerpt=item.get("excerpt") or item["text_normalized"][:220],
                        ref_id=item.get("ref_id", "")))
                    for c in item.get("categories", []):
                        if c not in cl.categories:
                            cl.categories.append(c)
                    # highest priority wins, keep its reason
                    order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "POSITIVE": 0}
                    if order.get(item.get("priority", "LOW"), 0) > order.get(cl.priority, 0):
                        cl.priority = item["priority"]
                        cl.priority_reason = item.get("priority_reason", "")
                    cl.confidence = max(cl.confidence, item.get("confidence", 0.5))
                    merged = True
                    break
        if not merged:
            clusters.append(Cluster(
                primary_text=item["text_normalized"],
                evidence=[EvidenceRef(
                    platform=item["platform"], source_name=item["source_name"],
                    ts=item.get("ts"), sender=item.get("sender", ""),
                    excerpt=item.get("excerpt") or item["text_normalized"][:220],
                    ref_id=item.get("ref_id", ""))],
                categories=list(item.get("categories", [])),
                priority=item.get("priority", "LOW"),
                priority_reason=item.get("priority_reason", ""),
                confidence=item.get("confidence", 0.5),
            ))
            tok_cache.append(toks)
    return clusters
