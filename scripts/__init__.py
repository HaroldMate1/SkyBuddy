"""SkyBuddy Flight Tracking System.

Complete flight tracking, monitoring, and recommendations for any agent.
Works with Hermes, OpenClaw, Claude, or standalone.
"""

__version__ = "1.0.0"
__author__ = "Harold Mateo"

from agent_integration import SkyBuddyAgent, create_agent, AgentType
from mcp_server import SkyBuddyMCPServer
from hermes_adapter import HermesAdapter, create_hermes_adapter
from openclaw_adapter import OpenClawAdapter, OpenClawMCPServer, create_openclaw_adapter

__all__ = [
    "SkyBuddyAgent",
    "create_agent",
    "AgentType",
    "SkyBuddyMCPServer",
    "HermesAdapter",
    "create_hermes_adapter",
    "OpenClawAdapter",
    "OpenClawMCPServer",
    "create_openclaw_adapter",
]
