import json

from src.categorization.keyword_taxonomy import (
    get_all_categories,
    get_all_keywords,
)
from src.models import Tool


def add_to_falkordb(tool_dict):
    """Add tool to graph."""
    tool: Tool = Tool.model_validate(tool_dict)


def add_tools():
    with open("tools.json") as f:
        tools = json.load(f)["tools"]
    for tool in tools:
        add_to_falkordb(tool)


def main():
    print(get_all_keywords())
    print(get_all_categories())


if __name__ == "__main__":
    main()
