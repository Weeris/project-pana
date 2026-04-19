"""Jurisdiction: Owns interest rates and ESG regulations for a region."""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Jurisdiction:
    """
    Attributes:
    - name: e.g. "EU", "US", "SG", "CN"
    - base_interest_rate: policy rate
    - carbon_tax_rate: USD per tonne CO₂
    - green_subsidy: fraction 0–1 of eligible green capex refunded
    - esg_disclosure_required: bool
    """

    name: str
    base_interest_rate: float = 0.02        # 2%
    carbon_tax_rate: float = 0.0            # 0 USD/tonne initially
    green_subsidy: float = 0.0             # 0% subsidy initially
    esg_disclosure_required: bool = True

    def apply_carbon_tax(self, emissions_tonnage: float) -> float:
        """Calculate carbon tax owed."""
        return emissions_tonnage * self.carbon_tax_rate

    def apply_green_subsidy(self, green_capex: float) -> float:
        """Calculate subsidy received for green capex."""
        return green_capex * self.green_subsidy

    def policy_summary(self) -> str:
        return (
            f"[{self.name}] IR={self.base_interest_rate:.2%}, "
            f"CarbonTax=${self.carbon_tax_rate}/t, "
            f"GreenSubsidy={self.green_subsidy:.0%}"
        )
