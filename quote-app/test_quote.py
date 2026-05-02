"""
Quick test of the quote engine (non-interactive).
Run: python test_quote.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from quote_engine import QuoteEngine

engine = QuoteEngine("output/pricing_data.json")

print("=== Quote Engine Test ===\n")
print("Dealer Groups:", engine.get_dealer_groups())
print()

# Test Group A
print("--- Group A Styles (door) ---")
print(engine.get_styles("Group A", "door"))
print()

print("--- Group A COLONIST TEXT Sizes ---")
print(engine.get_sizes("Group A", "COLONIST TEXT", "door")[:10])
print()

print("--- Group K CONMORE Bifold Sizes ---")
print(engine.get_sizes("Group K", "CONMORE", "bifold"))
print()

# Build a sample quote
q = engine.build_quote(
    dealer_group="Group A",
    product_type="door",
    style="COLONIST TEXT",
    size='12"',
    variant="HC",
    selected_addons=["Machining for 1 3/8\": 3 Hinges and Lock"],
    quantity=10,
)
print("--- Sample Quote: Group A COLONIST TEXT 12\" HC x10 ---")
for item in q["line_items"]:
    print(f"  {item['description']}: ${item['unit_price']:.2f} x {item['quantity']} = ${item['subtotal']:.2f}")
print(f"  TOTAL: ${q['total']:.2f}")
if q["errors"]:
    print("  ERRORS:", q["errors"])
print()

# Verify: 64.45 base + 9.55 machining = 74.00 per door × 10 = $740.00
assert abs(q["total"] - 740.00) < 0.01, f"Expected $740.00 got ${q['total']}"
print("PASS: Group A COLONIST TEXT 12\" HC x10 + machining = $740.00")

# Test Trimlite bifold
q2 = engine.build_quote(
    dealer_group="Trimlite",
    product_type="bifold",
    style="Colonial Moulded",
    size='18" to 24"',
    variant="HC-Bifold HC c/w Hardware",
    quantity=5,
)
print("\n--- Sample Quote: Trimlite Colonial Moulded Bifold 18-24\" x5 ---")
for item in q2["line_items"]:
    print(f"  {item['description']}: ${item['unit_price']:.2f} x {item['quantity']} = ${item['subtotal']:.2f}")
print(f"  TOTAL: ${q2['total']:.2f}")
print(f"  Errors: {q2['errors']}")

# Export to Excel
path = engine.export_quote_to_excel(q, "output/test_quote.xlsx")
print(f"\nExported quote to: {path}")
print("\nAll tests passed!")
