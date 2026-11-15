"""Every decision a build needs, named once, as DATA.

Ported from iacgenius-v2 services/workflow/app/decision_catalogue.py (CE replan Phase 1).
The CE keeps the full 15-key, provider-neutral catalogue: only COSTLY/IRREVERSIBLE keys can
ever interrupt (ASKABLE); CHEAP keys are defaulted and disclosed. CE v0.1 resolves from the
catalogue alone (no baseline/profile/knowledge sources yet) — see resolver.py.

A key here is a question the build cannot avoid answering. Whether it is answered by the user
(STATED) or by the catalogue fallback (SOURCE) is the resolver's job, and every answer is
recorded with its source. Reversibility is declared here once; a model never classifies it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A free-form value must be a plain identifier-ish token: a model answering "the cheapest
# region" has not stated a region, and settled values are shown to the worker as platform
# facts that must be incapable of carrying a sentence.
_FREE_FORM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

CHEAP = "cheap"
COSTLY = "costly"
IRREVERSIBLE = "irreversible"
REVERSIBILITY_CLASSES = (CHEAP, COSTLY, IRREVERSIBLE)
ASKABLE = frozenset({COSTLY, IRREVERSIBLE})


@dataclass(frozen=True)
class DecisionKey:
    key: str
    question: str
    reversibility: str
    domain: tuple[str, ...]
    why_it_matters: str

    def is_askable(self) -> bool:
        return self.reversibility in ASKABLE


def _k(key, question, reversibility, domain, why) -> DecisionKey:
    if reversibility not in REVERSIBILITY_CLASSES:
        raise ValueError(f"{key}: unknown reversibility {reversibility!r}")
    return DecisionKey(key=key, question=question, reversibility=reversibility, domain=domain,
                       why_it_matters=why)


KEYS: tuple[DecisionKey, ...] = (
    _k("target.provider", "Which cloud should this stack be built on?", IRREVERSIBLE,
       ("aws", "azure", "gcp"),
       "A stack targets exactly one cloud. Every resource, identity and network decision is "
       "realized on it, and moving clouds is a rebuild."),
    _k("target.iac_tool", "Which IaC tool should the code be written for?", IRREVERSIBLE,
       ("terraform", "opentofu"),
       "State, provider pins and dialect all follow the tool; switching is a migration of the "
       "state, not a find-and-replace."),
    _k("environment", "Is this for development, staging or production?", COSTLY,
       ("dev", "staging", "prod"),
       "It sets the strictness of nearly every other default. Building a prod stack with dev "
       "defaults is the single most expensive wrong answer here."),
    _k("region", "Which region should this run in?", COSTLY, (),
       "Moving a deployed stack between regions is a migration, not an edit, and region drives "
       "data residency and latency."),
    _k("network.exposure", "Should this be reachable from the public internet?", IRREVERSIBLE,
       ("public", "restricted", "private"),
       "Exposure is the largest single lever on blast radius, and a resource created inside a "
       "private network cannot be made public by editing one attribute."),
    _k("identity.model", "How should the workload authenticate to cloud services?", COSTLY,
       ("workload_identity", "static_credentials"),
       "Static credentials become a rotation obligation and a secret-scanning finding forever. "
       "Switching afterwards touches every caller."),
    _k("data.classification", "What is the most sensitive class of data this will hold?", COSTLY,
       ("public", "internal", "confidential", "regulated"),
       "It is the input a compliance lens reads. Classifying regulated data as internal produces "
       "a stack that passes checks it should have failed."),
    _k("encryption.key_owner", "Should encryption use your own key, or the provider's default key?",
       IRREVERSIBLE, ("provider_managed", "customer_managed"),
       "Most services cannot be re-keyed in place. Choosing provider-managed and later needing "
       "customer-managed means recreating the resource."),
    _k("data.retention_days", "How long should logs and backups be kept?", CHEAP, (),
       "A number that differs between organisations. It must come from policy rather than from a "
       "tool's hardcoded default."),
    _k("availability.target", "How much redundancy does this need?", COSTLY,
       ("single_zone", "multi_zone", "multi_region"),
       "It is the biggest driver of monthly cost after compute size, and raising it later often "
       "means recreating networking."),
    _k("scale.envelope", "Roughly what load should this be sized for?", CHEAP,
       ("low", "moderate", "high"),
       "Sizing is an edit. It is here so the number is disclosed rather than silently invented."),
    _k("state.backend", "Where should the IaC state live?", COSTLY,
       ("remote_managed", "remote_object_store", "local"),
       "State is the record of what exists. Moving it is a migration, and a local backend cannot "
       "be shared by a team."),
    _k("management.tier", "Should the stack use managed services, or do you need to run components yourself?",
       COSTLY, ("managed", "self_managed"),
       "Moving a managed data store or platform to one you run yourself (or back) is a migration. "
       "Managed is the platform's stance: less to patch, scale and secure."),
    _k("naming.prefix", "What prefix should resource names use?", CHEAP, (),
       "Renaming is usually a replace, but the cost is small and the default is obvious, so this "
       "is disclosed rather than asked."),
    _k("tagging.owner", "Who owns this workload?", CHEAP, (),
       "An untagged resource is the one nobody can attribute at cost-review time."),
)

KEYS_BY_ID: dict[str, DecisionKey] = {k.key: k for k in KEYS}

# The mission's own target: chosen at mission creation, never defaulted, never asked in the
# ordinary way. Changing either is a new mission, not an edit (owner target-lock requirement).
MISSION_TARGET_KEYS: dict[str, str] = {"target.provider": "provider", "target.iac_tool": "iac_tool"}

# COSTLY keys whose fallback SETTLES them, disclosed, instead of asking. Deliberately tiny:
# managed-first is the platform stance; the only route to self_managed is the person asking.
DISCLOSED_NOT_ASKED: frozenset[str] = frozenset({"management.tier"})

_NEUTRAL_DEFAULTS: dict[str, str] = {
    "environment": "dev",
    "network.exposure": "private",
    "identity.model": "workload_identity",
    "data.classification": "internal",
    "encryption.key_owner": "provider_managed",
    "data.retention_days": "30",
    "availability.target": "single_zone",
    "scale.envelope": "low",
    "state.backend": "remote_object_store",
    "naming.prefix": "iacg",
    "tagging.owner": "unassigned",
    "management.tier": "managed",
}

_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "aws": {"region": "us-east-1"},
    "azure": {"region": "eastus"},
    "gcp": {"region": "us-central1"},
}

# How a neutral value is realised on each provider (prompt material, not policy).
PROVIDER_TERMS: dict[tuple[str, str], str] = {
    ("aws", "encryption.key_owner"):
        "customer_managed means a customer-managed KMS key; provider_managed means the service "
        "default (SSE-S3, aws/<service> keys).",
    ("aws", "identity.model"):
        "workload_identity means an IAM role assumed by the service; static_credentials means "
        "long-lived access keys.",
    ("aws", "availability.target"):
        "multi_zone means resources spread across at least two availability zones.",
    ("aws", "state.backend"):
        "remote_object_store means an S3 backend with state locking.",
    ("aws", "management.tier"):
        "managed means services AWS operates (Lambda, Fargate, RDS, DynamoDB) over EC2 instances "
        "you patch and scale.",
}

_UNIVERSAL: tuple[str, ...] = tuple(k.key for k in KEYS)

# Shape a provider-specific value must have (a region list goes stale; a shape does not).
PROVIDER_SHAPES: dict[tuple[str, str], tuple[re.Pattern[str], str]] = {
    ("aws", "region"): (re.compile(r"^[a-z]{2}(-gov|-iso[a-z]?)?-[a-z]+-\d$"), "an AWS region such as us-east-1"),
    ("azure", "region"): (re.compile(r"^[a-z]+[a-z0-9]*$"), "an Azure region such as eastus or westeurope"),
    ("gcp", "region"): (re.compile(r"^[a-z]+-[a-z]+\d+$"), "a GCP region such as us-central1"),
}


def required_keys(provider: str, iac_tool: str) -> tuple[str, ...]:
    del provider, iac_tool  # universal today; keyed for the day one lane differs
    return _UNIVERSAL


def key(key_id: str) -> DecisionKey | None:
    return KEYS_BY_ID.get(key_id)


def reversibility(key_id: str) -> str:
    entry = KEYS_BY_ID.get(key_id)
    return entry.reversibility if entry else CHEAP


def is_askable(key_id: str) -> bool:
    entry = KEYS_BY_ID.get(key_id)
    return bool(entry and entry.is_askable())


def catalogue_default(provider: str, key_id: str) -> str | None:
    per_provider = _PROVIDER_DEFAULTS.get(provider or "", {})
    if key_id in per_provider:
        return per_provider[key_id]
    return _NEUTRAL_DEFAULTS.get(key_id)


def provider_term(provider: str, key_id: str) -> str | None:
    return PROVIDER_TERMS.get((provider or "", key_id))


def in_domain(key_id: str, value: str) -> bool:
    entry = KEYS_BY_ID.get(key_id)
    if entry is None:
        return False
    if not entry.domain:
        return bool(_FREE_FORM.match(str(value).strip()))
    return value in entry.domain


def provider_misfit(provider: str, key_id: str, value: str) -> str | None:
    shape = PROVIDER_SHAPES.get((provider or "", key_id))
    if shape is None or shape[0].match(str(value).strip()):
        return None
    return f"{value!r} is not {shape[1]}"


def describe(key_id: str, provider: str = "") -> str:
    entry = KEYS_BY_ID.get(key_id)
    if entry is None:
        return key_id
    domain = f" [{'|'.join(entry.domain)}]" if entry.domain else ""
    gloss = provider_term(provider, key_id)
    tail = f" {gloss}" if gloss else ""
    return f"{entry.key}{domain}: {entry.question}{tail}"
