"""
Exotiq SaaS Pricing Model

Used to calculate GHL opportunity monetary value (annual contract value).

Tiers:
  Starter (1-10 vehicles):     $29/vehicle/month, minimum $79/month
  Professional (11-25):        $399/month + overage
  Business (26-75):            $899/month + overage
  Enterprise (76+):            $1,799/month + overage

All values are ANNUAL (monthly * 12) for GHL opportunity monetary value.
"""


def calculate_annual_value(fleet_size: int | None) -> int:
    """Calculate annual SaaS contract value based on fleet size.
    
    Returns annual value in dollars (integer).
    If fleet_size is None or 0, estimates conservatively at Starter minimum.
    """
    if not fleet_size or fleet_size <= 0:
        # Unknown fleet -- assume Starter minimum
        return 79 * 12  # $948/yr

    if fleet_size <= 10:
        # Starter: $29/vehicle/month, minimum $79/month
        monthly = max(fleet_size * 29, 79)
        return monthly * 12

    if fleet_size <= 25:
        # Professional: $399/month
        return 399 * 12  # $4,788/yr

    if fleet_size <= 75:
        # Business: $899/month
        return 899 * 12  # $10,788/yr

    # Enterprise: 76+ vehicles, $1,799/month
    return 1799 * 12  # $21,588/yr


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
