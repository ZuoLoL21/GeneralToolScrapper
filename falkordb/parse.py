import json

from model_tool import Tool

with open("tools.json") as f:
    tools = json.load(f)["tools"]
for tool in tools:
    add_to_falkordb(tool)


def add_to_falkordb(tool):
    """Add tool to graph."""