from __future__ import annotations

from visualize.message_utils import prepare_messages_for_api


def test_repair_orphaned_tool_use() -> None:
    messages = [
        {"role": "user", "content": "Build PDF"},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "toolu_abc", "name": "generate_pdf", "input": {}},
            ],
        },
        {"role": "user", "content": "Build the recommended Excel report"},
    ]
    prepared = prepare_messages_for_api(messages)
    assert len(prepared) == 4
    assert prepared[2]["role"] == "user"
    assert prepared[2]["content"][0]["type"] == "tool_result"
    assert prepared[2]["content"][0]["tool_use_id"] == "toolu_abc"
    assert prepared[3]["content"] == "Build the recommended Excel report"


def test_strip_extra_fields_from_text_blocks() -> None:
    messages = [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "hello",
                    "parsed_output": {"unexpected": True},
                },
            ],
        },
    ]
    prepared = prepare_messages_for_api(messages)
    block = prepared[0]["content"][0]
    assert block == {"type": "text", "text": "hello"}
    assert "parsed_output" not in block


def test_preserve_valid_tool_pair() -> None:
    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "toolu_x", "name": "generate_pdf", "input": {}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_x", "content": "{}"},
            ],
        },
        {"role": "assistant", "content": "Done"},
    ]
    prepared = prepare_messages_for_api(messages)
    assert len(prepared) == 4
