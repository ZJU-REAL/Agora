"""Bounded lexical interests and explicit locality matching, without models."""

import math
import re
import unicodedata
from collections import defaultdict

STOP_WORDS = frozenset(
    [
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "have",
        "from",
        "about",
        "into",
        "your",
        "what",
        "would",
        "could",
        "should",
        "there",
        "here",
        "some",
        "more",
        "very",
        "only",
        "after",
        "before",
        "doing",
        "make",
        "made",
        "just",
        "one",
        "two",
        "are",
        "was",
        "were",
        "has",
        "had",
        "you",
        "our",
        "their",
        "they",
        "them",
        "its",
        "not",
        "but",
        "can",
        "will",
        "how",
        "why",
        "when",
        "where",
        "looking",
        "interested",
        "trying",
        "learning",
        "share",
        "experience",
        "observation",
    ]
)


def normalize_text(text):
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).casefold().split())


def text_terms(text, limit=48):
    normalized = normalize_text(text)[:1024]
    terms = set(re.findall(r"[a-z][a-z0-9'-]{2,}", normalized)) - STOP_WORDS
    for run in re.findall(r"[\u3400-\u9fff]+", normalized):
        terms.update(run[i : i + 2] for i in range(len(run) - 1))
    return set(sorted(terms)[:limit])


def profile_text_interests(persona):
    result = defaultdict(float)
    for topic, weight in persona.get("interests", {}).items():
        terms = text_terms(topic) | {normalize_text(topic)}
        for term in terms:
            if term:
                result[term] += float(weight)
    for topic in persona.get("niches", []):
        for term in text_terms(topic):
            result[term] += 0.5
    for text in [persona.get("bio", ""), *persona.get("example_posts", [])[:4]]:
        for term in text_terms(text):
            result[term] += 0.15
    return {term: max(-3.0, min(3.0, weight)) for term, weight in result.items()}


def text_affinity(interests, text):
    tokens = text_terms(text)
    normalized = normalize_text(text)[:1024]
    matched = [
        term
        for term in interests
        if term in tokens
        or (re.search(r"[\u3400-\u9fff]", term) and term in normalized)
    ]
    value = sum(interests[term] for term in matched) / math.sqrt(max(1, len(matched)))
    return max(-3.0, min(3.0, value))


def locality_parts(value):
    value = normalize_text(value)
    parts = re.split(r"\s*[/>,，|]\s*", value)
    result = set()
    for part in parts:
        units = re.findall(r"[^省市区县]+[省市区县]", part)
        if units:
            result.update(unit.strip() for unit in units)
            result.update(unit[:-1].strip() for unit in units)
        if part and len(units) < 2:
            result.add(part)
            result.add(re.sub(r"[省市区县]$", "", part))
    return result


class LocalityMatcher:
    def __init__(self, aliases=None):
        aliases = {} if aliases is None else aliases
        if not isinstance(aliases, dict) or len(aliases) > 64:
            raise ValueError("location_aliases must be a mapping of at most 64 places")
        self.aliases = {}
        for canonical, names in aliases.items():
            if not isinstance(canonical, str) or not canonical.strip():
                raise ValueError("Location names must be nonempty strings")
            if not isinstance(names, list) or len(names) > 16:
                raise ValueError("Location aliases must be lists of at most 16 names")
            for name in [canonical, *names]:
                if not isinstance(name, str) or not name.strip() or len(name) > 100:
                    raise ValueError("Location aliases must be short strings")
                key = normalize_text(name)
                target = normalize_text(canonical)
                if key in self.aliases and self.aliases[key] != target:
                    raise ValueError(
                        "Location aliases cannot refer to different places"
                    )
                self.aliases[key] = target

    def matches(self, value, query):
        wanted = normalize_text(query)
        if not wanted:
            return False
        query_parts = {self.aliases.get(part, part) for part in locality_parts(wanted)}
        actual_parts = {self.aliases.get(part, part) for part in locality_parts(value)}
        # A complete district/path query must match all its supplied levels.
        return bool(query_parts) and query_parts <= actual_parts
