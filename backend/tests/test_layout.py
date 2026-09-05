from app.layout import deterministic_layout_review, merge_layout_reviews
from app.models import LayoutFinding, LayoutReview, UiSpecification


def specification() -> UiSpecification:
    return UiSpecification.model_validate(
        {
            "screen_name": "Checkout",
            "platform": "mobile",
            "viewport_width": 390,
            "viewport_height": 844,
            "summary": "Mobile checkout",
            "root": {"id": "root", "kind": "container", "name": "Page", "children": []},
        }
    )


def test_deterministic_review_blocks_incomplete_assembly() -> None:
    review = deterministic_layout_review(
        specification(),
        {
            "bounds": {"width": 430, "height": 800},
            "instances": 1,
            "placeholders": 1,
            "overlaps": {"summary": {"bySeverity": {"major": 1}}},
        },
        expected_instances=2,
    )

    assert review.status == "invalid"
    assert {item.category for item in review.findings} == {
        "viewport-overflow",
        "component-coverage",
        "unbound-placeholder",
        "overlap",
    }


def test_deterministic_failure_cannot_be_overridden_by_semantic_review() -> None:
    deterministic = LayoutReview(
        status="invalid",
        summary="Geometry failed.",
        findings=[
            LayoutFinding(
                severity="error",
                category="overflow",
                evidence="Too wide",
                correction="Resize",
            )
        ],
    )
    semantic = LayoutReview(status="valid", summary="Semantics look good.")

    assert merge_layout_reviews(deterministic, semantic).status == "invalid"
