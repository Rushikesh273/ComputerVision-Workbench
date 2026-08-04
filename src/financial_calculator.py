"""
financial_calculator.py
========================
Material Giveaway calculator.

Formulas:
    Weight Drift           = Actual Weight - Target Weight
    Percentage Difference  = (Weight Drift / Target Weight) * 100
    Material Giveaway      = max(0, Weight Drift)
    Cost per Packet        = Material Giveaway (kg) * Cost per Kg
    Total Daily Loss       = Cost per Packet * Packets per Day
    Total Monthly Loss     = Total Daily Loss * Days per Month

Units: weights in grams, cost in Rupees per kg, all money in Rupees.
Underfill (actual < target) gives Material Giveaway = 0, never negative.
"""

import unittest


class MaterialGiveawayCalculator:
    """
    Bundles target weight, actual weight, and cost per kg so each
    calculation method just reads self.* instead of repeating the same
    arguments in every function call.

    packets_per_day / days_per_month are optional (default 1 / 30) --
    only needed if you call total_daily_loss()/total_monthly_loss();
    the core four values (weight drift, giveaway, cost per packet,
    total loss) don't require them at all.
    """

    def __init__(self, target_weight_g, actual_weight_g, cost_per_kg,
                 packets_per_day=1, days_per_month=30):
        self.target_weight_g = target_weight_g
        self.actual_weight_g = actual_weight_g
        self.cost_per_kg = cost_per_kg
        self.packets_per_day = packets_per_day
        self.days_per_month = days_per_month

    def weight_difference(self):
        """Weight Drift = Actual Weight - Target Weight (grams)."""
        return self.actual_weight_g - self.target_weight_g

    def percentage_difference(self):
        """Weight Drift as a % of target weight."""
        return (self.weight_difference() / self.target_weight_g) * 100

    def material_giveaway(self):
        """max(0, Weight Drift). Underfill -> 0, never negative."""
        return max(0, self.weight_difference())

    def cost_per_packet(self):
        """Material Giveaway (kg) * Cost per Kg, in Rupees. This IS the
        total loss for one packet."""
        giveaway_kg = self.material_giveaway() / 1000
        return round(giveaway_kg * self.cost_per_kg, 2)

    def total_daily_loss(self):
        """Cost per Packet * Packets per Day, in Rupees. (Needs packets_per_day.)"""
        return round(self.cost_per_packet() * self.packets_per_day, 2)

    def total_monthly_loss(self):
        """Total Daily Loss * Days per Month, in Rupees. (Needs packets_per_day.)"""
        return round(self.total_daily_loss() * self.days_per_month, 2)

    def report(self):
        """Return the four core results: Weight Drift, Giveaway, Cost per Packet, Total Loss."""
        return {
            "weight_drift_g": self.weight_difference(),
            "giveaway_g": self.material_giveaway(),
            "cost_per_packet_rs": self.cost_per_packet(),
            "total_loss_rs": self.cost_per_packet(),  # loss for this packet
        }


# ============================================================================
# UNIT TESTS
# Tests use fixed known values (task sample: target=1000g, actual=1018g,
# cost=Rs250/kg) so results are checkable by hand.
# ============================================================================

class TestMaterialGiveawayCalculator(unittest.TestCase):

    def setUp(self):
        self.calc = MaterialGiveawayCalculator(
            target_weight_g=1000, actual_weight_g=1018, cost_per_kg=250
        )
        self.underfill_calc = MaterialGiveawayCalculator(
            target_weight_g=1000, actual_weight_g=985, cost_per_kg=250
        )

    def test_weight_difference(self):
        self.assertEqual(self.calc.weight_difference(), 18)
        self.assertEqual(self.underfill_calc.weight_difference(), -15)

    def test_percentage_difference(self):
        self.assertAlmostEqual(self.calc.percentage_difference(), 1.8)

    def test_material_giveaway(self):
        self.assertEqual(self.calc.material_giveaway(), 18)
        self.assertEqual(self.underfill_calc.material_giveaway(), 0)  # floors, not negative

    def test_cost_per_packet(self):
        self.assertAlmostEqual(self.calc.cost_per_packet(), 4.5)
        self.assertEqual(self.underfill_calc.cost_per_packet(), 0.0)

    def test_total_daily_loss(self):
        calc = MaterialGiveawayCalculator(1000, 1018, 250, packets_per_day=10000)
        self.assertEqual(calc.total_daily_loss(), 45000.0)

    def test_total_monthly_loss(self):
        calc = MaterialGiveawayCalculator(1000, 1018, 250, packets_per_day=10000)
        self.assertEqual(calc.total_monthly_loss(), 1350000.0)


# ============================================================================
# INTERACTIVE DEMO
# Asks for exactly the 3 inputs (Target Weight, Actual
# Weight, Material Cost) and prints exactly the 4 outputs the task asked
# for (Weight Drift, Giveaway, Cost per Packet, Total Loss).
# ============================================================================

if __name__ == "__main__":
    print("Material Giveaway Calculator\n")

    target_weight = float(input("Target weight (g): "))
    actual_weight = float(input("Actual weight (g): "))
    cost_per_kg = float(input("Material cost (Rs/kg): "))

    calc = MaterialGiveawayCalculator(target_weight, actual_weight, cost_per_kg)
    r = calc.report()

    print("\n--- Results ---")
    print(f"Weight Drift:  {r['weight_drift_g']} g")
    print(f"Giveaway:      {r['giveaway_g']} g")
    print(f"Cost per Packet: Rs {r['cost_per_packet_rs']}")
    print(f"Total Loss:    Rs {r['total_loss_rs']}")