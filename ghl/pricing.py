"""
Exotiq SaaS Pricing Model

Used to calculate GHL opportunity monetary value (annual contract value).
Uses ANNUAL pricing (save 2 months vs monthly).

Tiers:
  Starter (1-10 vehicles):     $290/vehicle/year, minimum $79/year
  Professional (up to 25):     $3,990/year ($22/vehicle overage)
  Business (up to 75):         $8,990/year ($18/vehicle overage)
  Enterprise (up to 150):      $17,990/year ($15/vehicle overage)

GHL opportunity values use annual pricing as the default assumption.
"""


def calculate_annual_value(fleet_size: int | None) -> int:
    """Calculate annual SaaS contract value based on fleet size.
    
    Returns annual value in dollars (integer).
    If fleet_size is None or 0, estimates conservatively at Starter minimum.
    """
    if not fleet_size or fleet_size <= 0:
        # Unknown fleet -- assume Starter minimum
        return 79  # $79/yr minimum

    if fleet_size <= 10:
        # Starter: $290/vehicle/year, minimum $79/year
        return max(fleet_size * 290, 79)

    if fleet_size <= 25:
        # Professional: $3,990/year
        return 3990

    if fleet_size <= 75:
        # Business: $8,990/year
        return 8990

    # Enterprise: up to 150 vehicles, $17,990/year
    return 17990


def get_tier_name(fleet_size: int | None) -> str:
    """Return the pricing tier name for a given fleet size."""
    if not fleet_size or fleet_size <= 0:
        return "Starter (est.)"
    if fleet_size <= 10:
        return "Starter"
    if fleet_size <= 25:
        return "Professional"
    if fleet_size <= 75:
        return "Business"
    return "Enterprise"
