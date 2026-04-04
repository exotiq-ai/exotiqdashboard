"""
Exotiq SaaS Pricing Model

Used to calculate GHL opportunity monetary value (annual contract value).
Uses ANNUAL pricing (save 2 months vs monthly).

Tiers (monthly, billed monthly):
  Starter (1-10 vehicles):     $29/vehicle/month, minimum $79/month
  Professional (up to 25):     $399/month
  Business (up to 75):         $899/month
  Enterprise (up to 150):      $1,799/month

GHL opportunity values use monthly * 12 as pipeline estimate.
Post-conversion, update to actual contract value (monthly or annual).
"""


def calculate_annual_value(fleet_size: int | None) -> int:
    """Calculate annual SaaS contract value based on fleet size.
    
    Returns annual value in dollars (integer).
    If fleet_size is None or 0, estimates conservatively at Starter minimum.
    """
    if not fleet_size or fleet_size <= 0:
        return 79 * 12  # Starter minimum, monthly * 12

    if fleet_size <= 10:
        return max(fleet_size * 29, 79) * 12  # $29/vehicle/month
    if fleet_size <= 25:
        return 399 * 12  # Professional
    if fleet_size <= 75:
        return 899 * 12  # Business
    return 1799 * 12  # Enterprise


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
