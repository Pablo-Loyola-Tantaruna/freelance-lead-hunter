from datetime import datetime, timezone
from hunter.config import STACK_GROUPS, INTENT_TERMS, GEO_POSITIVE, CORE_QUERIES, QUERY_GROUPS
from hunter.lead_hunter import current_query_group

name, active = current_query_group()
print("=== STACK / SKILLS ===")
for group, values in STACK_GROUPS.items():
    print(f"\n{group}:")
    print("  " + ", ".join(values))
print("\n=== INTENT ===")
print("  " + ", ".join(INTENT_TERMS))
print("\n=== GEO / REMOTE ===")
print("  " + ", ".join(GEO_POSITIVE))
print("\n=== ROTATION ===")
print(f"UTC now: {datetime.now(timezone.utc).isoformat()}")
print(f"Active group: {name}")
for q in active:
    print("  -", q)
print("\nAll groups:")
for group, qs in QUERY_GROUPS.items():
    print(f"  {group}: {len(qs)} rotating queries")
print(f"  core: {len(CORE_QUERIES)} every run")
