import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
print(os.getcwd())

# test import
from backend.app.agents.shared.base_agent import BaseAgent
