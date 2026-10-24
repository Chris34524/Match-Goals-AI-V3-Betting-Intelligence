"""Declarative contract only. TypedDict does not validate values at runtime.

See docs/v3/data-contract.md for constraints, provenance and eligibility rules.
All keys are required; unknown values are explicitly None (JSON null).
"""

from typing import List, Literal, Optional, TypedDict


SCHEMA_VERSION = "3.0.0"
FEATURE_VERSION = "3.0.0"


class Metadata(TypedDict):
    source: str
    match_id: str
    date: Optional[str]
    kickoff: Optional[str]
    country: Optional[str]
    competition: Optional[str]
    season: Optional[str]
    home_team: Optional[str]
    away_team: Optional[str]


class TeamSample(TypedDict):
    history_count: Optional[int]
    venue_history_count: Optional[int]
    xg_count: Optional[int]
    xga_count: Optional[int]


class Inputs(TypedDict):
    home: TeamSample
    away: TeamSample
    bilateral_xg_available: Optional[bool]
    standings_available: Optional[bool]
    h2h_available: Optional[bool]
    h2h_count: Optional[int]


class Provenance(TypedDict):
    group: Literal["metadata", "inputs", "predictions", "labels"]
    field: str
    source: str
    artifact: Optional[str]
    observed_at: Optional[str]
    available_at: Optional[str]


class Audit(TypedDict):
    feature_cutoff: Optional[str]
    temporal_status: Literal["OK", "REVIEW", "ERROR"]
    eligible: bool
    reasons: List[str]
    quality_flags: Optional[List[str]]
    provenance: List[Provenance]


class ChampionPrediction(TypedDict):
    model: Literal["J_BT_sin_temporada"]
    generated_at: Optional[str]
    lambda_home: Optional[float]
    lambda_away: Optional[float]
    lambda_total: Optional[float]
    p_over_1_5: Optional[float]
    p_over_2_5: Optional[float]
    p_over_3_5: Optional[float]
    p_over_4_5: Optional[float]
    p_btts: Optional[float]
    p_home: Optional[float]
    p_draw: Optional[float]
    p_away: Optional[float]
    confidence: Optional[str]
    global_quality: Optional[str]
    flags: Optional[List[str]]


class Labels(TypedDict):
    settled_at: Optional[str]
    home_goals: Optional[int]
    away_goals: Optional[int]
    total_goals: Optional[int]
    label_btts: Optional[bool]
    label_over_1_5: Optional[bool]
    label_over_2_5: Optional[bool]
    label_over_3_5: Optional[bool]
    label_over_4_5: Optional[bool]
    label_1x2: Optional[Literal["1", "X", "2"]]


class CanonicalMatch(TypedDict):
    schema_version: Literal["3.0.0"]
    feature_version: Literal["3.0.0"]
    metadata: Metadata
    inputs: Inputs
    audit: Audit
    predictions: Optional[ChampionPrediction]
    labels: Optional[Labels]
