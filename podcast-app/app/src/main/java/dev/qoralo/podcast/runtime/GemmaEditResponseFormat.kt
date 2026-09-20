package dev.qoralo.podcast.runtime

import org.json.JSONArray
import org.json.JSONObject

/** Constrains generation, not a response repair. Existing strict parser and semantic validators remain authoritative. */
internal const val EDIT_RESPONSE_FORMAT_VERSION = "edit-revision-json-schema-v1"
internal const val CHAPTER_RESPONSE_FORMAT_VERSION = "chapter-json-schema-v1"
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

/**
 * The requested identity is pinned with `const`, so a wrong or episode-level ID cannot be decoded at all.
 * Length is deliberately unconstrained: a grammar cannot guarantee completion inside the output ceiling.
 */
internal fun chapterResponseSchema(chapter: OutlineChapter): String = JSONObject()
    .put("type", "object")
    .put("additionalProperties", false)
    .put("properties", JSONObject()
        .put("id", JSONObject().put("type", "string").put("const", chapter.id))
        .put("title", JSONObject().put("type", "string").put("const", chapter.title))
        .put("text", JSONObject().put("type", "string").put("minLength", 1)))
    .put("required", JSONArray(listOf("id", "title", "text")))
    .toString()

internal fun responseSchemaForMode(mode: String): String? = if (mode == "edit") EDIT_REVISION_JSON_SCHEMA else null
