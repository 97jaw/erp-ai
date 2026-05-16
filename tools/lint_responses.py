from __future__ import annotations

import json
import sys

from gateway.quality_validation import validate_response_quality

SAMPLE_RESPONSES = [
    {
        "text": "Abu Dhabi Police leads with AED 10.5M (67.3% of the total).",
        "visualization": {
            "visual_type": "BAR_CHART",
            "data": {"labels": ["Abu Dhabi Police"], "values": [10500000]},
        },
    },
    {
        "text": "amount_total:sum is 0",
        "visualization": {"visual_type": "DATA_TABLE", "data": {"rows": []}},
    },
]


def main() -> int:
    failures = 0
    for index, response in enumerate(SAMPLE_RESPONSES, start=1):
        passed, issues = validate_response_quality(response)
        if passed:
            continue
        failures += 1
        print(f"Sample {index} failed quality checks: {json.dumps(issues)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
