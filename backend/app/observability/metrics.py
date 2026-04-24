"""Minimal CloudWatch Embedded Metric Format helpers."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger("metrics")


def emit_metric(
    metric_name: str,
    value: int | float,
    *,
    unit: str = "Count",
    namespace: str = "AgentMetrics",
    dimensions: Mapping[str, str] | None = None,
    properties: Mapping[str, Any] | None = None,
) -> None:
    """Emit a single EMF metric record to CloudWatch Logs."""
    emit_metrics(
        metrics=[{"Name": metric_name, "Unit": unit, "Value": value}],
        namespace=namespace,
        dimensions=dimensions,
        properties=properties,
    )


def emit_metrics(
    *,
    metrics: list[dict[str, Any]],
    namespace: str = "AgentMetrics",
    dimensions: Mapping[str, str] | None = None,
    properties: Mapping[str, Any] | None = None,
) -> None:
    """Emit a batch of EMF metrics without extra dependencies."""
    dimension_data = dict(dimensions or {})
    emf_metrics = [
        {"Name": metric["Name"], "Unit": metric.get("Unit", "Count")} for metric in metrics
    ]

    payload: dict[str, Any] = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": namespace,
                    "Dimensions": [list(dimension_data.keys())],
                    "Metrics": emf_metrics,
                }
            ],
        },
        **dimension_data,
    }

    for metric in metrics:
        payload[metric["Name"]] = metric["Value"]

    if properties:
        payload.update(properties)

    logger.info(json.dumps(payload, default=str, ensure_ascii=True))
