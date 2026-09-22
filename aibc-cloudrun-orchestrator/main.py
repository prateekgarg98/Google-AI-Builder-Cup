from google.cloud import discoveryengine_v1
from google import genai
from google.genai.types import GenerateContentConfig, HttpOptions
from google.protobuf.json_format import MessageToDict


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ID = "ai-builder-cup-2026"

# Discovery Engine
DISCOVERY_LOCATION = "global"
ENGINE_ID = "aibc-search-engine-ewa"
SERVING_CONFIG_ID = "default_config"

# Gemini / Vertex AI
GEMINI_LOCATION = "global"
GEMINI_MODEL = "gemini-2.5-flash"

# Retrieval
TOP_K = 6
MAX_EXTRACTIVE_ANSWERS = 1
MAX_EXTRACTIVE_SEGMENTS = 2
NUM_PREVIOUS_SEGMENTS = 1
NUM_NEXT_SEGMENTS = 1


# ============================================================
# CLIENTS
# ============================================================

discovery_client = discoveryengine_v1.SearchServiceClient()

gemini_client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=GEMINI_LOCATION,
    http_options=HttpOptions(api_version="v1"),
)


# ============================================================
# PROTOBUF HELPERS
# ============================================================

def get_dict(message):
    """
    Convert a protobuf message to a normal Python dictionary.
    """
    if message is None:
        return {}

    try:
        return MessageToDict(
            message._pb,
            preserving_proto_field_name=False,
        )
    except Exception:
        try:
            return MessageToDict(
                message,
                preserving_proto_field_name=False,
            )
        except Exception:
            return {}


def get_content_from_items(items):
    """
    Extract text from extractive answer/segment objects.
    """
    contents = []

    if not items:
        return contents

    for item in items:
        if isinstance(item, dict):
            value = (
                item.get("content")
                or item.get("text")
                or item.get("answer")
                or item.get("snippet")
            )

            if value:
                contents.append(value)

    return contents


# ============================================================
# EXTRACTIVE CONTENT PARSING
# ============================================================

def parse_extractive_content(document_dict, search_result_dict=None):
    """
    Extract extractive answers and segments from Discovery Engine.

    Discovery Engine response structures can vary depending on
    API/client versions, so several possible locations are checked.
    """

    extractive_answers = []
    extractive_segments = []

    sources = []

    if search_result_dict:
        sources.append(search_result_dict)

    if document_dict:
        sources.append(document_dict)

    for source in sources:

        # ----------------------------------------------------
        # Direct fields
        # ----------------------------------------------------

        for key in [
            "extractiveAnswers",
            "extractive_answers",
        ]:
            value = source.get(key)

            if value:
                extractive_answers.extend(
                    get_content_from_items(value)
                )

        for key in [
            "extractiveSegments",
            "extractive_segments",
        ]:
            value = source.get(key)

            if value:
                extractive_segments.extend(
                    get_content_from_items(value)
                )

        # ----------------------------------------------------
        # derivedStructData
        # ----------------------------------------------------

        derived = source.get("derivedStructData", {})

        if isinstance(derived, dict):

            for key in [
                "extractiveAnswers",
                "extractive_answers",
            ]:
                value = derived.get(key)

                if value:
                    extractive_answers.extend(
                        get_content_from_items(value)
                    )

            for key in [
                "extractiveSegments",
                "extractive_segments",
            ]:
                value = derived.get(key)

                if value:
                    extractive_segments.extend(
                        get_content_from_items(value)
                    )

    # --------------------------------------------------------
    # Deduplicate while preserving order
    # --------------------------------------------------------

    extractive_answers = list(
        dict.fromkeys(extractive_answers)
    )

    extractive_segments = list(
        dict.fromkeys(extractive_segments)
    )

    return extractive_answers, extractive_segments


# ============================================================
# DISCOVERY ENGINE SEARCH
# ============================================================

def search_discovery_engine(query):

    serving_config = (
        f"projects/{PROJECT_ID}"
        f"/locations/{DISCOVERY_LOCATION}"
        f"/collections/default_collection"
        f"/engines/{ENGINE_ID}"
        f"/servingConfigs/{SERVING_CONFIG_ID}"
    )

    extractive_spec = (
        discoveryengine_v1.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
            max_extractive_answer_count=MAX_EXTRACTIVE_ANSWERS,
            max_extractive_segment_count=MAX_EXTRACTIVE_SEGMENTS,
            num_previous_segments=NUM_PREVIOUS_SEGMENTS,
            num_next_segments=NUM_NEXT_SEGMENTS,
        )
    )

    content_search_spec = (
        discoveryengine_v1.SearchRequest.ContentSearchSpec(
            extractive_content_spec=extractive_spec
        )
    )

    request = discoveryengine_v1.SearchRequest(
        serving_config=serving_config,
        query=query,
        page_size=TOP_K,
        content_search_spec=content_search_spec,
    )

    response = discovery_client.search(request=request)

    return parse_results(response)


# ============================================================
# PARSE SEARCH RESULTS
# ============================================================

def parse_results(response):

    results = []

    for search_result in response:

        search_result_dict = get_dict(search_result)

        document = search_result.document

        document_dict = get_dict(document)

        # ----------------------------------------------------
        # Document ID
        # ----------------------------------------------------

        document_id = document_dict.get("id")

        if not document_id:

            name = document_dict.get("name", "")

            if name:
                document_id = name.split("/")[-1]

        # ----------------------------------------------------
        # Structured metadata
        # ----------------------------------------------------

        struct_data = document_dict.get(
            "structData",
            {}
        )

        if not isinstance(struct_data, dict):
            struct_data = {}

        # ----------------------------------------------------
        # Filename
        # ----------------------------------------------------

        filename = (
            struct_data.get("filename")
            or struct_data.get("fileName")
            or document_dict.get("filename")
            or document_dict.get("fileName")
            or document_id
        )

        # ----------------------------------------------------
        # Category
        # ----------------------------------------------------

        category = (
            struct_data.get("category")
            or document_dict.get("category")
            or "unknown"
        )

        # ----------------------------------------------------
        # Extractive content
        # ----------------------------------------------------

        (
            extractive_answers,
            extractive_segments,
        ) = parse_extractive_content(
            document_dict,
            search_result_dict,
        )

        # ----------------------------------------------------
        # Document contexts
        # ----------------------------------------------------

        document_contexts = []

        content = document_dict.get("content")

        if isinstance(content, dict):

            text = (
                content.get("text")
                or content.get("content")
            )

            if text:
                document_contexts.append(text)

        elif isinstance(content, str):

            document_contexts.append(content)

        # ----------------------------------------------------
        # Store result
        # ----------------------------------------------------

        results.append(
            {
                "document_id": document_id,
                "filename": filename,
                "category": category,
                "extractive_answers": extractive_answers,
                "extractive_segments": extractive_segments,
                "document_contexts": document_contexts,
            }
        )

    return results


# ============================================================
# BUILD GROUNDED CONTEXT
# ============================================================

def build_context(results):

    context_blocks = []

    for index, result in enumerate(results, start=1):

        filename = result["filename"]
        category = result["category"]

        pieces = []

        # ----------------------------------------------------
        # Prefer document content
        # ----------------------------------------------------

        pieces.extend(
            result.get("document_contexts", [])
        )

        # ----------------------------------------------------
        # Then extractive segments
        # ----------------------------------------------------

        if not pieces:

            pieces.extend(
                result.get("extractive_segments", [])
            )

        # ----------------------------------------------------
        # Then extractive answers
        # ----------------------------------------------------

        if not pieces:

            pieces.extend(
                result.get("extractive_answers", [])
            )

        # ----------------------------------------------------
        # Deduplicate
        # ----------------------------------------------------

        pieces = list(dict.fromkeys(pieces))

        if not pieces:
            continue

        context_text = "\n".join(pieces)

        context_blocks.append(
            f"""
SOURCE {index}
Filename: {filename}
Category: {category}

Content:
{context_text}
""".strip()
        )

    return "\n\n==============================\n\n".join(
        context_blocks
    )


# ============================================================
# GEMINI ANSWER GENERATION
# ============================================================

def generate_answer(query, context):

    if not context.strip():

        return (
            "I could not find sufficient enterprise "
            "knowledge to answer this question."
        )

    system_instruction = """
You are an Enterprise Knowledge Assistant.

Answer the user's question ONLY using the provided
enterprise knowledge retrieved from the company's
knowledge base.

Rules:

1. Do not invent facts.
2. Do not use information that is not supported by
   the retrieved context.
3. If the retrieved information is insufficient,
   explicitly say so.
4. Prefer precise procedural information.
5. Preserve important requirements, conditions,
   exceptions and sequence of actions.
6. Mention the relevant source filename when useful.
7. Do not claim that an action was executed.
8. Distinguish documented requirements from
   recommendations or interpretations.
"""

    prompt = f"""
{system_instruction}

============================================================
ENTERPRISE KNOWLEDGE
============================================================

{context}

============================================================
USER QUESTION
============================================================

{query}

============================================================
ANSWER
============================================================
"""

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=800,
        ),
    )

    return response.text


# ============================================================
# HTTP CLOUD RUN FUNCTION
# ============================================================

def enterprise_work_agent(request):

    try:

        # ----------------------------------------------------
        # Parse request
        # ----------------------------------------------------

        request_json = request.get_json(
            silent=True
        )

        if not request_json:
            request_json = {}

        query = request_json.get(
            "query",
            "What are the requirements for a production deployment and what should happen if the deployment fails?"
        )

        # ----------------------------------------------------
        # Discovery Engine
        # ----------------------------------------------------

        results = search_discovery_engine(query)

        # ----------------------------------------------------
        # Build context
        # ----------------------------------------------------

        context = build_context(results)

        # ----------------------------------------------------
        # Gemini
        # ----------------------------------------------------

        answer = generate_answer(
            query,
            context,
        )

        # ----------------------------------------------------
        # Return complete response
        # ----------------------------------------------------

        return {
            "status": "success",
            "query": query,
            "answer": answer,
            "retrieval": {
                "top_k": TOP_K,
                "result_count": len(results),
                "results": results,
            },
        }

    except Exception as e:

        print(
            "ENTERPRISE WORK AGENT ERROR:",
            repr(e),
        )

        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error": str(e),
        }, 500