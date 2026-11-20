from __future__ import annotations

from app.modules.conversation.tools import TOOL_SPECS, tool_prompt


def test_tool_specs_are_wrapped_and_descriptive() -> None:
    names = {spec["function"]["name"] for spec in TOOL_SPECS}
    assert {"read_task_files", "read_task_file", "save_artifact", "create_execution"} <= names

    for spec in TOOL_SPECS:
        function = spec["function"]
        assert spec["type"] == "function"
        assert function["description"].strip()
        parameters = function["parameters"]
        assert parameters["type"] == "object"
        assert "properties" in parameters
        assert "required" in parameters
        for field, meta in parameters["properties"].items():
            assert meta.get("description"), f"{function['name']}.{field} 缺少说明"

    reader = next(
        spec for spec in TOOL_SPECS if spec["function"]["name"] == "read_task_file"
    )
    fields = reader["function"]["parameters"]["properties"]
    assert {"file_id", "filename", "offset", "limit"} <= set(fields)

    prompt = tool_prompt()
    for spec in TOOL_SPECS:
        function = spec["function"]
        assert function["name"] in prompt
        assert function["description"] in prompt
