from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).with_name("rules.json")


class UnknownRuleType(KeyError):
    pass


@dataclass(frozen=True)
class RuleReference:
    document: str
    clause: str
    url: str


@dataclass(frozen=True)
class RuleType:
    type_id: str
    family: str
    name_ru: str
    description_ru: str
    reference: RuleReference


class RuleCatalog:
    def __init__(self, types: dict[str, RuleType]):
        self._types = types

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "RuleCatalog":
        raw = json.loads(path.read_text(encoding="utf-8"))
        documents = raw["documents"]
        types: dict[str, RuleType] = {}
        for item in raw["types"]:
            doc = documents[item["normative"]["document_id"]]
            types[item["type_id"]] = RuleType(
                type_id=item["type_id"],
                family=item["family"],
                name_ru=item["name_ru"],
                description_ru=item["description_ru"],
                reference=RuleReference(document=doc["document"], clause=item["normative"].get("clause", ""), url=doc["url"]),
            )
        return cls(types)

    def get(self, type_id: str) -> RuleType:
        try:
            return self._types[type_id]
        except KeyError as e:
            raise UnknownRuleType(type_id) from e

    def all(self) -> list[RuleType]:
        return list(self._types.values())
