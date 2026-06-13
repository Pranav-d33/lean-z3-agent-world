import Lake
open Lake

package agent_world where
  -- No external dependencies — just Lean core + native_decide

@[default_target]
lean_lib AgentWorld where
  roots := #[]
