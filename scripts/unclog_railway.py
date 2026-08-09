"""Unclog script — release stuck BUSY agents on Railway whose negotiations are rejected.

Usage: python scripts/unclog_railway.py
"""

import requests, sys

BASE = "https://agent-sync-production.up.railway.app/api/v1"

# Get all agents and negotiations
agents = requests.get(f"{BASE}/agents", timeout=5).json()
negs = requests.get(f"{BASE}/negotiations", timeout=5).json()

# Find rejected negotiations
rejected = [n for n in negs.get("negotiations", []) if n["status"] == "REJECTED"]
print(f"Rejected negotiations: {len(rejected)}")

# Map agent IDs to names
agent_map = {a["agent_id"]: a for a in agents.get("agents", [])}

for n in rejected:
    a1_id = n["agent_1_id"]
    a2_id = n["agent_2_id"]
    a1 = agent_map.get(a1_id, {})
    a2 = agent_map.get(a2_id, {})

    print(f"\nSession: {n['session_id'][:16]}...")
    print(f"  Agent 1: {a1.get('display_name', a1_id)} — status={a1.get('status')}")
    print(f"  Agent 2: {a2.get('display_name', a2_id)} — status={a2.get('status')}")

    if a1.get("status") == "BUSY":
        print(f"  STUCK: {a1.get('display_name')} is BUSY on a REJECTED negotiation")
    if a2.get("status") == "BUSY":
        print(f"  STUCK: {a2.get('display_name')} is BUSY on a REJECTED negotiation")

print("\n=== SUMMARY ===")
stuck = [a for a in agents.get("agents", []) if a["status"] == "BUSY"]
print(f"BUSY agents: {len(stuck)}")
for a in stuck:
    # Check if their negation is rejected
    agent_negs = [n for n in negs.get("negotiations", [])
                  if n["agent_1_id"] == a["agent_id"] or n["agent_2_id"] == a["agent_id"]]
    for an in agent_negs:
        print(f"  {a['display_name'][:30]:30s} → negotiation {an['session_id'][:16]}... status={an['status']}")
