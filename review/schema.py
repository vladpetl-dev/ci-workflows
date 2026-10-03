"""JSON schema the model's answer must follow (structured output)."""

SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": SEVERITIES},
                    "category": {"type": "string", "enum": ["security", "quality"]},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                "required": ["severity", "category", "file", "line", "title",
                             "description", "recommendation"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "findings"],
    "additionalProperties": False,
}
