from typing import Any

from .models import LayoutFinding, LayoutReview, UiSpecification


def deterministic_layout_review(
    specification: UiSpecification,
    telemetry: dict[str, Any],
    expected_instances: int,
) -> LayoutReview:
    findings: list[LayoutFinding] = []
    bounds = telemetry.get("bounds") or {}
    width = _number(bounds, "width", "w")
    height = _number(bounds, "height", "h")
    if width is None or height is None:
        findings.append(
            LayoutFinding(
                severity="error",
                category="telemetry",
                evidence="OpenPencil did not return measurable page bounds.",
                correction="Re-open the output document and repeat layout inspection.",
            )
        )
    elif width > specification.viewport_width + 2:
        findings.append(
            LayoutFinding(
                severity="error",
                category="viewport-overflow",
                node_ids=[str(telemetry.get("root_node_id", ""))],
                evidence=f"Page width {width:.1f}px exceeds viewport {specification.viewport_width}px.",
                correction="Use fill sizing or recompose wide rows for the target viewport.",
            )
        )

    instances = int(telemetry.get("instances", 0))
    if instances != expected_instances:
        findings.append(
            LayoutFinding(
                severity="error",
                category="component-coverage",
                evidence=f"Created {instances} of {expected_instances} resolved component instances.",
                correction="Restore missing placeholders and insert every approved binding.",
            )
        )

    placeholders = int(telemetry.get("placeholders", 0))
    if placeholders:
        findings.append(
            LayoutFinding(
                severity="error",
                category="unbound-placeholder",
                evidence=f"{placeholders} component placeholders remain on the generated page.",
                correction="Resolve or explicitly remove every placeholder before final review.",
            )
        )

    overlap = telemetry.get("overlaps") or {}
    summary = overlap.get("summary") or {}
    by_severity = summary.get("bySeverity") or summary.get("by_severity") or {}
    severe = int(by_severity.get("critical", 0)) + int(by_severity.get("major", 0))
    if severe:
        findings.append(
            LayoutFinding(
                severity="error",
                category="overlap",
                evidence=f"OpenPencil detected {severe} major or critical overlap findings.",
                correction="Fix unintended intersections and parent overflow before approval.",
            )
        )

    touch_targets = telemetry.get("small_touch_targets") or []
    if touch_targets and specification.platform in {"mobile", "responsive"}:
        findings.append(
            LayoutFinding(
                severity="warning",
                category="touch-target",
                node_ids=[str(item.get("id")) for item in touch_targets[:12]],
                evidence=f"{len(touch_targets)} interactive instances are smaller than 44×44px.",
                correction="Use a larger component size or increase its surrounding hit area.",
            )
        )

    status = "invalid" if any(item.severity == "error" for item in findings) else "valid"
    summary_text = (
        "Deterministic layout checks found blocking issues."
        if status == "invalid"
        else "Deterministic geometry and binding checks passed."
    )
    return LayoutReview(status=status, summary=summary_text, findings=findings)


def merge_layout_reviews(
    deterministic: LayoutReview,
    semantic: LayoutReview,
) -> LayoutReview:
    findings = [*deterministic.findings, *semantic.findings]
    status = "invalid" if (deterministic.status == "invalid" or semantic.status == "invalid") else "valid"
    return LayoutReview(
        status=status,
        summary=f"{deterministic.summary} {semantic.summary}".strip(),
        findings=findings,
    )


def _number(value: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        item = value.get(key)
        if isinstance(item, int | float):
            return float(item)
    return None
