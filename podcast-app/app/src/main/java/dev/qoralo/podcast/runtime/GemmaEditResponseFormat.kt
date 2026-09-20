package dev.qoralo.podcast.runtime

/** Constrains generation, not a response repair. Existing strict parser and semantic validators remain authoritative. */
internal const val EDIT_RESPONSE_FORMAT_VERSION = "edit-revision-json-schema-v1"
internal val EDIT_REVISION_JSON_SCHEMA = """
    {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "schemaVersion": {"type": "integer", "enum": [1]},
        "title": {"type": "string", "minLength": 1},
        "chapters": {
          "type": "array", "minItems": 1, "maxItems": 20,
          "items": {
            "type": "object", "additionalProperties": false,
            "properties": {
              "id": {"type": "string", "minLength": 1},
              "title": {"type": "string", "minLength": 1},
              "text": {"type": "string", "minLength": 1}
            },
            "required": ["id", "title", "text"]
          }
        },
        "summary": {"type": "string", "minLength": 1}
      },
      "required": ["schemaVersion", "title", "chapters", "summary"]
    }
""".trimIndent()

internal fun responseSchemaForMode(mode: String): String? = if (mode == "edit") EDIT_REVISION_JSON_SCHEMA else null
