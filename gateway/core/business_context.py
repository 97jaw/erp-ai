"""Elrace-specific business context and industry norms.

Provides company identity, fiscal calendar, UAE construction benchmarks,
and reference data that shapes financial and operational responses.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BusinessContext:
    """Information about the business that shapes responses."""

    company_name: str = "Elrace Cos. & Gen. Cont. CO."
    company_id: int = 1
    currency: str = "AED"
    fiscal_year_start: int = 1
    fiscal_year_end: int = 12

    industry: str = "Construction & Facilities Management"
    geography: str = "UAE"

    business_norms: dict[str, Any] = field(
        default_factory=lambda: {
            "healthy_gross_margin": (15, 30),
            "concerning_dso": 90,
            "vat_rate": 5,
            "weekend": ["Friday", "Saturday"],
        }
    )

    top_clients: list[str] = field(
        default_factory=lambda: [
            "Abu Dhabi Police",
            "National Guard",
            "Civil Defense",
            "Ministry of Interior",
        ]
    )

    def summary(self) -> str:
        """Format business context for inclusion in Claude system prompt."""
        healthy_margin = self.business_norms["healthy_gross_margin"]
        return f"""
Company: {self.company_name}
Currency: {self.currency}
Fiscal Year: Jan-Dec
Industry: {self.industry}
Geography: {self.geography}

Healthy gross margin: {healthy_margin[0]}-{healthy_margin[1]}%
Concerning DSO threshold: {self.business_norms['concerning_dso']} days
"""
