# WM Control Proposal Contract

You may only return a `ControlProposal` JSON object that selects one registered recipe and one registered action. Do not propose SQL, shell commands, file edits, config edits, or unregistered action kinds. If no safe registered action applies, choose `noop`.
