
import sys
import json
from pathlib import Path

# Setup paths
sys.path.append('D:/WOW/wm-project/src')
sys.path.append('D:/WOW/wm-project/src/wm')

from wm.control.models import ControlProposal
from wm.control.coordinator import ControlCoordinator
from wm.llm.proposal_adapter import ProposalAdapter, ProposalKind

# 1. Setup Mocks
print("[Test] Initializing Project components...")
adapter = ProposalAdapter(registry=None) # registry not needed for this simple test
coordinator = ControlCoordinator(registry=None)

# 2. Simulate a valid Watcher request (as if it found an event)
print("[Test] Simulating event found by Watcher...")
mock_req = ControlProposal(
    id="fake_event_id",
    action_kind="announcement",
    proposal_metadata={
        "id": "propose_my_announcement",
        "context": {
            "intent": "Hello, I am the World Master!",
            "player_guid": 1,
            "provenance": {"source": "watcher"}
        }
    }
)

# 3. Run the Pipeline
print("[Test] Processing Proposal...")
proposal = adapter.propose(mock_req)
print(f"   Proposal Created: {proposal.intent} ({proposal.kind})")

command = coordinator.process_proposal(proposal)

if command:
    print(f"[Test] RESULT SUCCESS: Executing Command -> {command}")
else:
    print("[Test] RESULT FAILED: No command generated.")
