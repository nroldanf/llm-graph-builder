OPENAI_MODELS = ["openai-gpt-3.5", "openai-gpt-4o", "openai-gpt-4o-mini"]
GEMINI_MODELS = ["gemini-1.0-pro", "gemini-1.5-pro", "gemini-1.5-flash"]
GROQ_MODELS = ["groq-llama3"]
BUCKET_UPLOAD = 'llm-graph-builder-upload'
BUCKET_FAILED_FILE = 'llm-graph-builder-failed'
PROJECT_ID = 'llm-experiments-387609' 
GRAPH_CHUNK_LIMIT = 50 


#query 
GRAPH_QUERY = """
MATCH docs = (d:Document) 
WHERE d.fileName IN $document_names
WITH docs, d 
ORDER BY d.createdAt DESC

// Fetch chunks for documents, currently with limit
CALL {{
  WITH d
  OPTIONAL MATCH chunks = (d)<-[:PART_OF|FIRST_CHUNK]-(c:Chunk)
  RETURN c, chunks LIMIT {graph_chunk_limit}
}}

WITH collect(distinct docs) AS docs, 
     collect(distinct chunks) AS chunks, 
     collect(distinct c) AS selectedChunks

// Select relationships between selected chunks
WITH *, 
     [c IN selectedChunks | 
       [p = (c)-[:NEXT_CHUNK|SIMILAR]-(other) 
       WHERE other IN selectedChunks | p]] AS chunkRels

// Fetch entities and relationships between entities
CALL {{
  WITH selectedChunks
  UNWIND selectedChunks AS c
  OPTIONAL MATCH entities = (c:Chunk)-[:HAS_ENTITY]->(e)
  OPTIONAL MATCH entityRels = (e)--(e2:!Chunk) 
  WHERE exists {{
    (e2)<-[:HAS_ENTITY]-(other) WHERE other IN selectedChunks
  }}
  RETURN entities, entityRels, collect(DISTINCT e) AS entity
}}

WITH docs, chunks, chunkRels, 
     collect(entities) AS entities, 
     collect(entityRels) AS entityRels, 
     entity

WITH *

CALL {{
  WITH entity
  UNWIND entity AS n
  OPTIONAL MATCH community = (n:__Entity__)-[:IN_COMMUNITY]->(p:__Community__)
  OPTIONAL MATCH parentcommunity = (p)-[:PARENT_COMMUNITY*]->(p2:__Community__) 
  RETURN collect(community) AS communities, 
         collect(parentcommunity) AS parentCommunities
}}

WITH apoc.coll.flatten(docs + chunks + chunkRels + entities + entityRels + communities + parentCommunities, true) AS paths

// Distinct nodes and relationships
CALL {{
  WITH paths 
  UNWIND paths AS path 
  UNWIND nodes(path) AS node 
  WITH distinct node 
  RETURN collect(node /* {{.*, labels:labels(node), elementId:elementId(node), embedding:null, text:null}} */) AS nodes 
}}

CALL {{
  WITH paths 
  UNWIND paths AS path 
  UNWIND relationships(path) AS rel 
  RETURN collect(distinct rel) AS rels 
}}  

RETURN nodes, rels

"""

CHUNK_QUERY = """
MATCH (chunk:Chunk)
WHERE chunk.id IN $chunksIds
MATCH (chunk)-[:PART_OF]->(d:Document)

WITH d, 
     collect(distinct chunk) AS chunks

// Collect relationships and nodes
WITH d, chunks, 
     collect {
         MATCH ()-[r]->() 
         WHERE elementId(r) IN $relationshipIds
         RETURN r
     } AS rels,
     collect {
         MATCH (e) 
         WHERE elementId(e) IN $entityIds
         RETURN e
     } AS nodes

WITH d, 
     chunks, 
     apoc.coll.toSet(apoc.coll.flatten(rels)) AS rels, 
     nodes

RETURN 
    d AS doc, 
    [chunk IN chunks | 
        chunk {.*, embedding: null, element_id: elementId(chunk)}
    ] AS chunks,
    [
        node IN nodes | 
        {
            element_id: elementId(node),
            labels: labels(node),
            properties: {
                id: node.id,
                description: node.description
            }
        }
    ] AS nodes,
    [
        r IN rels | 
        {
            startNode: {
                element_id: elementId(startNode(r)),
                labels: labels(startNode(r)),
                properties: {
                    id: startNode(r).id,
                    description: startNode(r).description
                }
            },
            endNode: {
                element_id: elementId(endNode(r)),
                labels: labels(endNode(r)),
                properties: {
                    id: endNode(r).id,
                    description: endNode(r).description
                }
            },
            relationship: {
                type: type(r),
                element_id: elementId(r)
            }
        }
    ] AS entities
"""

COUNT_CHUNKS_QUERY = """
MATCH (d:Document {fileName: $file_name})<-[:PART_OF]-(c:Chunk)
RETURN count(c) AS total_chunks
"""

CHUNK_TEXT_QUERY = """
MATCH (d:Document {fileName: $file_name})<-[:PART_OF]-(c:Chunk)
RETURN c.text AS chunk_text, c.position AS chunk_position, c.page_number AS page_number
ORDER BY c.position
SKIP $skip
LIMIT $limit
"""

NODEREL_COUNT_QUERY_WITH_COMMUNITY = """
MATCH (d:Document)
WHERE d.fileName IS NOT NULL
OPTIONAL MATCH (d)<-[po:PART_OF]-(c:Chunk)
OPTIONAL MATCH (c)-[he:HAS_ENTITY]->(e:__Entity__)
OPTIONAL MATCH (c)-[sim:SIMILAR]->(c2:Chunk)
OPTIONAL MATCH (c)-[nc:NEXT_CHUNK]->(c3:Chunk)
OPTIONAL MATCH (e)-[ic:IN_COMMUNITY]->(comm:__Community__)
OPTIONAL MATCH (comm)-[pc1:PARENT_COMMUNITY]->(first_level:__Community__)
OPTIONAL MATCH (first_level)-[pc2:PARENT_COMMUNITY]->(second_level:__Community__)
OPTIONAL MATCH (second_level)-[pc3:PARENT_COMMUNITY]->(third_level:__Community__)
WITH
  d.fileName AS filename,
  count(DISTINCT c) AS chunkNodeCount,
  count(DISTINCT po) AS partOfRelCount,
  count(DISTINCT he) AS hasEntityRelCount,
  count(DISTINCT sim) AS similarRelCount,
  count(DISTINCT nc) AS nextChunkRelCount,
  count(DISTINCT e) AS entityNodeCount,
  collect(DISTINCT e) AS entities,
  count(DISTINCT comm) AS baseCommunityCount,
  count(DISTINCT first_level) AS firstlevelcommCount,
  count(DISTINCT second_level) AS secondlevelcommCount,
  count(DISTINCT third_level) AS thirdlevelcommCount,
  count(DISTINCT ic) AS inCommunityCount,
  count(DISTINCT pc1) AS parentCommunityRelCount1,
  count(DISTINCT pc2) AS parentCommunityRelCount2,
  count(DISTINCT pc3) AS parentCommunityRelCount3
WITH
  filename,
  chunkNodeCount,
  partOfRelCount + hasEntityRelCount + similarRelCount + nextChunkRelCount AS chunkRelCount,
  entityNodeCount,
  entities,
  baseCommunityCount + firstlevelcommCount + secondlevelcommCount + thirdlevelcommCount AS commCount,
  inCommunityCount + parentCommunityRelCount1 + parentCommunityRelCount2 + parentCommunityRelCount3 AS communityRelCount
CALL (entities) {
  UNWIND entities AS e
  RETURN sum(COUNT { (e)-->(e2:__Entity__) WHERE e2 in entities }) AS entityEntityRelCount
}
RETURN
  filename,
  COALESCE(chunkNodeCount, 0) AS chunkNodeCount,
  COALESCE(chunkRelCount, 0) AS chunkRelCount,
  COALESCE(entityNodeCount, 0) AS entityNodeCount,
  COALESCE(entityEntityRelCount, 0) AS entityEntityRelCount,
  COALESCE(commCount, 0) AS communityNodeCount,
  COALESCE(communityRelCount, 0) AS communityRelCount
"""
NODEREL_COUNT_QUERY_WITHOUT_COMMUNITY = """
MATCH (d:Document)
WHERE d.fileName = $document_name
OPTIONAL MATCH (d)<-[po:PART_OF]-(c:Chunk)
OPTIONAL MATCH (c)-[he:HAS_ENTITY]->(e:__Entity__)
OPTIONAL MATCH (c)-[sim:SIMILAR]->(c2:Chunk)
OPTIONAL MATCH (c)-[nc:NEXT_CHUNK]->(c3:Chunk)
WITH
  d.fileName AS filename,
  count(DISTINCT c) AS chunkNodeCount,
  count(DISTINCT po) AS partOfRelCount,
  count(DISTINCT he) AS hasEntityRelCount,
  count(DISTINCT sim) AS similarRelCount,
  count(DISTINCT nc) AS nextChunkRelCount,
  count(DISTINCT e) AS entityNodeCount,
  collect(DISTINCT e) AS entities
WITH
  filename,
  chunkNodeCount,
  partOfRelCount + hasEntityRelCount + similarRelCount + nextChunkRelCount AS chunkRelCount,
  entityNodeCount,
  entities
CALL (entities) {
  UNWIND entities AS e
  RETURN sum(COUNT { (e)-->(e2:__Entity__) WHERE e2 in entities }) AS entityEntityRelCount
}
RETURN
  filename,
  COALESCE(chunkNodeCount, 0) AS chunkNodeCount,
  COALESCE(chunkRelCount, 0) AS chunkRelCount,
  COALESCE(entityNodeCount, 0) AS entityNodeCount,
  COALESCE(entityEntityRelCount, 0) AS entityEntityRelCount
"""


## CHAT SETUP
CHAT_MAX_TOKENS = 1000
CHAT_SEARCH_KWARG_SCORE_THRESHOLD = 0.5
CHAT_DOC_SPLIT_SIZE = 3000
CHAT_EMBEDDING_FILTER_SCORE_THRESHOLD = 0.10

CHAT_TOKEN_CUT_OFF = {
     ('openai_gpt_3.5','azure_ai_gpt_35',"gemini_1.0_pro","gemini_1.5_pro", "gemini_1.5_flash","groq-llama3",'groq_llama3_70b','anthropic_claude_3_5_sonnet','fireworks_llama_v3_70b','bedrock_claude_3_5_sonnet', ) : 4, 
     ("openai-gpt-4","diffbot" ,'azure_ai_gpt_4o',"openai_gpt_4o", "openai_gpt_4o_mini") : 28,
     ("ollama_llama3") : 2  
}  

### CHAT TEMPLATES 
CHAT_SYSTEM_TEMPLATE = """
You are an AI-powered question-answering agent. Your task is to provide accurate and comprehensive responses to user queries based on the given context, chat history, and available resources.

### Response Guidelines:
1. **Direct Answers**: Provide clear and thorough answers to the user's queries without headers unless requested. Avoid speculative responses.
2. **Utilize History and Context**: Leverage relevant information from previous interactions, the current user input, and the context provided below.
3. **No Greetings in Follow-ups**: Start with a greeting in initial interactions. Avoid greetings in subsequent responses unless there's a significant break or the chat restarts.
4. **Admit Unknowns**: Clearly state if an answer is unknown. Avoid making unsupported statements.
5. **Avoid Hallucination**: Only provide information based on the context provided. Do not invent information.
6. **Response Length**: Keep responses concise and relevant. Aim for clarity and completeness within 4-5 sentences unless more detail is requested.
7. **Tone and Style**: Maintain a professional and informative tone. Be friendly and approachable.
8. **Error Handling**: If a query is ambiguous or unclear, ask for clarification rather than providing a potentially incorrect answer.
9. **Fallback Options**: If the required information is not available in the provided context, provide a polite and helpful response. Example: "I don't have that information right now." or "I'm sorry, but I don't have that information. Is there something else I can help with?"
10. **Context Availability**: If the context is empty, do not provide answers based solely on internal knowledge. Instead, respond appropriately by indicating the lack of information.


**IMPORTANT** : DO NOT ANSWER FROM YOUR KNOWLEDGE BASE USE THE BELOW CONTEXT

### Context:
<context>
{context}
</context>

### Example Responses:
User: Hi 
AI Response: 'Hello there! How can I assist you today?'

User: "What is Langchain?"
AI Response: "Langchain is a framework that enables the development of applications powered by large language models, such as chatbots. It simplifies the integration of language models into various applications by providing useful tools and components."

User: "Can you explain how to use memory management in Langchain?"
AI Response: "Langchain's memory management involves utilizing built-in mechanisms to manage conversational context effectively. It ensures that the conversation remains coherent and relevant by maintaining the history of interactions and using it to inform responses."

User: "I need help with PyCaret's classification model."
AI Response: "PyCaret simplifies the process of building and deploying machine learning models. For classification tasks, you can use PyCaret's setup function to prepare your data. After setup, you can compare multiple models to find the best one, and then fine-tune it for better performance."

User: "What can you tell me about the latest realtime trends in AI?"
AI Response: "I don't have that information right now. Is there something else I can help with?"

Note: This system does not generate answers based solely on internal knowledge. It answers from the information provided in the user's current and previous inputs, and from the context.
"""

QUESTION_TRANSFORM_TEMPLATE = "Given the below conversation, generate a search query to look up in order to get information relevant to the conversation. Only respond with the query, nothing else." 

## CHAT QUERIES
VECTOR_SEARCH_TOP_K = 10 # 5

VECTOR_SEARCH_QUERY = """
WITH node AS chunk, score
MATCH (chunk)-[:PART_OF]->(d:Document)
WITH d, 
     collect(distinct {chunk: chunk, score: score}) AS chunks, 
     avg(score) AS avg_score

WITH d, avg_score, 
     [c IN chunks | c.chunk.text] AS texts, 
     [c IN chunks | {id: c.chunk.id, score: c.score}] AS chunkdetails

WITH d, avg_score, chunkdetails, 
     apoc.text.join(texts, "\n----\n") AS text

RETURN text, 
       avg_score AS score, 
       {source: COALESCE(CASE WHEN d.url CONTAINS "None" 
                             THEN d.fileName 
                             ELSE d.url 
                       END, 
                       d.fileName), 
        chunkdetails: chunkdetails} AS metadata
""" 

### Vector graph search 
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT = 40
VECTOR_GRAPH_SEARCH_EMBEDDING_MIN_MATCH = 0.3
VECTOR_GRAPH_SEARCH_EMBEDDING_MAX_MATCH = 0.9
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT_MINMAX_CASE = 20
VECTOR_GRAPH_SEARCH_ENTITY_LIMIT_MAX_CASE = 40

VECTOR_GRAPH_SEARCH_QUERY_PREFIX = """
WITH node as chunk, score
// find the document of the chunk
MATCH (chunk)-[:PART_OF]->(d:Document)
// aggregate chunk-details
WITH d, collect(DISTINCT {chunk: chunk, score: score}) AS chunks, avg(score) as avg_score
// fetch entities
CALL { WITH chunks
UNWIND chunks as chunkScore
WITH chunkScore.chunk as chunk
"""

VECTOR_GRAPH_SEARCH_ENTITY_QUERY = """
    OPTIONAL MATCH (chunk)-[:HAS_ENTITY]->(e)
    WITH e, count(*) AS numChunks 
    ORDER BY numChunks DESC 
    LIMIT {no_of_entites}

    WITH 
    CASE 
        WHEN e.embedding IS NULL OR ({embedding_match_min} <= vector.similarity.cosine($query_vector, e.embedding) AND vector.similarity.cosine($query_vector, e.embedding) <= {embedding_match_max}) THEN 
            collect {{
                OPTIONAL MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){{0,1}}(:!Chunk&!Document&!__Community__) 
                RETURN path LIMIT {entity_limit_minmax_case}
            }}
        WHEN e.embedding IS NOT NULL AND vector.similarity.cosine($query_vector, e.embedding) >  {embedding_match_max} THEN
            collect {{
                OPTIONAL MATCH path=(e)(()-[rels:!HAS_ENTITY&!PART_OF]-()){{0,2}}(:!Chunk&!Document&!__Community__) 
                RETURN path LIMIT {entity_limit_max_case} 
            }} 
        ELSE 
            collect {{ 
                MATCH path=(e) 
                RETURN path 
            }}
    END AS paths, e
"""

# VECTOR_GRAPH_SEARCH_QUERY_SUFFIX = """
#     WITH apoc.coll.toSet(apoc.coll.flatten(collect(DISTINCT paths))) AS paths, 
#          collect(DISTINCT e) AS entities

#     // De-duplicate nodes and relationships across chunks
#     RETURN 
#         collect {
#             UNWIND paths AS p 
#             UNWIND relationships(p) AS r 
#             RETURN DISTINCT r
#         } AS rels,
#         collect {
#             UNWIND paths AS p 
#             UNWIND nodes(p) AS n 
#             RETURN DISTINCT n
#         } AS nodes, 
#         entities
# }

# // Generate metadata and text components for chunks, nodes, and relationships
# WITH d, avg_score,
#      [c IN chunks | c.chunk.text] AS texts, 
#      [c IN chunks | {id: c.chunk.id, score: c.score}] AS chunkdetails,
#      [n IN nodes | elementId(n)] AS entityIds,
#      [r IN rels | elementId(r)] AS relIds,
#      apoc.coll.sort([
#          n IN nodes | 
#          coalesce(apoc.coll.removeAll(labels(n), ['__Entity__'])[0], "") + ":" + 
#          n.id + 
#          (CASE WHEN n.description IS NOT NULL THEN " (" + n.description + ")" ELSE "" END)
#      ]) AS nodeTexts,
#      apoc.coll.sort([
#          r IN rels | 
#          coalesce(apoc.coll.removeAll(labels(startNode(r)), ['__Entity__'])[0], "") + ":" + 
#          startNode(r).id + " " + type(r) + " " + 
#          coalesce(apoc.coll.removeAll(labels(endNode(r)), ['__Entity__'])[0], "") + ":" + endNode(r).id
#      ]) AS relTexts,
#      entities

# // Combine texts into response text
# WITH d, avg_score, chunkdetails, entityIds, relIds,
#      "Text Content:\n" + apoc.text.join(texts, "\n----\n") +
#      "\n----\nEntities:\n" + apoc.text.join(nodeTexts, "\n") +
#      "\n----\nRelationships:\n" + apoc.text.join(relTexts, "\n") AS text, 
#      entities

# RETURN 
#     text, 
#     avg_score AS score, 
#     {
#         length: size(text), 
#         source: COALESCE(CASE WHEN d.url CONTAINS "None" THEN d.fileName ELSE d.url END, d.fileName), 
#         chunkdetails: chunkdetails, 
#         entities : {
#             entityids: entityIds, 
#             relationshipids: relIds
#         }
#     } AS metadata
# """
VECTOR_GRAPH_SEARCH_QUERY_SUFFIX = """
   WITH apoc.coll.toSet(apoc.coll.flatten(collect(DISTINCT paths))) AS paths,
        collect(DISTINCT e) AS entities
   // De-duplicate nodes and relationships across chunks
   RETURN
       collect {
           UNWIND paths AS p
           UNWIND relationships(p) AS r
           RETURN DISTINCT r
       } AS rels,
       collect {
           UNWIND paths AS p
           UNWIND nodes(p) AS n
           RETURN DISTINCT n
       } AS nodes,
       entities
}
// Generate metadata and text components for chunks, nodes, and relationships
WITH d, avg_score,
    [c IN chunks | c.chunk.text] AS texts,
    [c IN chunks | {id: c.chunk.id, score: c.score}] AS chunkdetails,
    [n IN nodes | elementId(n)] AS entityIds,
    [r IN rels | elementId(r)] AS relIds,
    apoc.coll.sort([
        n IN nodes |
        coalesce(apoc.coll.removeAll(labels(n), ['__Entity__'])[0], "") + ":" +
        coalesce(
            n.id,
            n[head([k IN keys(n) WHERE k =~ "(?i)(name|title|id|description)$"])],
            ""
        ) +
        (CASE WHEN n.description IS NOT NULL THEN " (" + n.description + ")" ELSE "" END)
    ]) AS nodeTexts,
    apoc.coll.sort([
        r IN rels |
        coalesce(apoc.coll.removeAll(labels(startNode(r)), ['__Entity__'])[0], "") + ":" +
        coalesce(
            startNode(r).id,
            startNode(r)[head([k IN keys(startNode(r)) WHERE k =~ "(?i)(name|title|id|description)$"])],
            ""
        ) + " " + type(r) + " " +
        coalesce(apoc.coll.removeAll(labels(endNode(r)), ['__Entity__'])[0], "") + ":" +
        coalesce(
            endNode(r).id,
            endNode(r)[head([k IN keys(endNode(r)) WHERE k =~ "(?i)(name|title|id|description)$"])],
            ""
        )
    ]) AS relTexts,
    entities
// Combine texts into response text
WITH d, avg_score, chunkdetails, entityIds, relIds,
    "Text Content:\n" + apoc.text.join(texts, "\n----\n") +
    "\n----\nEntities:\n" + apoc.text.join(nodeTexts, "\n") +
    "\n----\nRelationships:\n" + apoc.text.join(relTexts, "\n") AS text,
    entities
RETURN
   text,
   avg_score AS score,
   {
       length: size(text),
       source: COALESCE(CASE WHEN d.url CONTAINS "None" THEN d.fileName ELSE d.url END, d.fileName),
       chunkdetails: chunkdetails,
       entities : {
           entityids: entityIds,
           relationshipids: relIds
       }
   } AS metadata
"""

VECTOR_GRAPH_SEARCH_QUERY = VECTOR_GRAPH_SEARCH_QUERY_PREFIX+ VECTOR_GRAPH_SEARCH_ENTITY_QUERY.format(
    no_of_entites=VECTOR_GRAPH_SEARCH_ENTITY_LIMIT,
    embedding_match_min=VECTOR_GRAPH_SEARCH_EMBEDDING_MIN_MATCH,
    embedding_match_max=VECTOR_GRAPH_SEARCH_EMBEDDING_MAX_MATCH,
    entity_limit_minmax_case=VECTOR_GRAPH_SEARCH_ENTITY_LIMIT_MINMAX_CASE,
    entity_limit_max_case=VECTOR_GRAPH_SEARCH_ENTITY_LIMIT_MAX_CASE
) + VECTOR_GRAPH_SEARCH_QUERY_SUFFIX

### Local community search
LOCAL_COMMUNITY_TOP_K = 10
LOCAL_COMMUNITY_TOP_CHUNKS = 3
LOCAL_COMMUNITY_TOP_COMMUNITIES = 3
LOCAL_COMMUNITY_TOP_OUTSIDE_RELS = 10

LOCAL_COMMUNITY_SEARCH_QUERY = """
WITH collect(node) AS nodes, 
     avg(score) AS score, 
     collect({{entityids: elementId(node), score: score}}) AS metadata

WITH score, nodes, metadata,

     collect {{
         UNWIND nodes AS n
         MATCH (n)<-[:HAS_ENTITY]->(c:Chunk)
         WITH c, count(distinct n) AS freq
         RETURN c
         ORDER BY freq DESC
         LIMIT {topChunks}
     }} AS chunks,

     collect {{
         UNWIND nodes AS n
         OPTIONAL MATCH (n)-[:IN_COMMUNITY]->(c:__Community__)
         WITH c, c.community_rank AS rank, c.weight AS weight
         RETURN c
         ORDER BY rank, weight DESC
         LIMIT {topCommunities}
     }} AS communities,

     collect {{
         UNWIND nodes AS n
         UNWIND nodes AS m
         MATCH (n)-[r]->(m)
         RETURN DISTINCT r
         // TODO: need to add limit
     }} AS rels,

     collect {{
         UNWIND nodes AS n
         MATCH path = (n)-[r]-(m:__Entity__)
         WHERE NOT m IN nodes
         WITH m, collect(distinct r) AS rels, count(*) AS freq
         ORDER BY freq DESC 
         LIMIT {topOutsideRels}
         WITH collect(m) AS outsideNodes, apoc.coll.flatten(collect(rels)) AS rels
         RETURN {{ nodes: outsideNodes, rels: rels }}
     }} AS outside
"""

LOCAL_COMMUNITY_SEARCH_QUERY_SUFFIX = """
RETURN {
  chunks: [c IN chunks | c.text],
  communities: [c IN communities | c.summary],
  entities: [
    n IN nodes | 
    CASE 
      WHEN size(labels(n)) > 1 THEN 
        apoc.coll.removeAll(labels(n), ["__Entity__"])[0] + ":" + n.id + " " + coalesce(n.description, "")
      ELSE 
        n.id + " " + coalesce(n.description, "")
    END
  ],
  relationships: [
    r IN rels | 
    startNode(r).id + " " + type(r) + " " + endNode(r).id
  ],
  outside: {
    nodes: [
      n IN outside[0].nodes | 
      CASE 
        WHEN size(labels(n)) > 1 THEN 
          apoc.coll.removeAll(labels(n), ["__Entity__"])[0] + ":" + n.id + " " + coalesce(n.description, "")
        ELSE 
          n.id + " " + coalesce(n.description, "")
      END
    ],
    relationships: [
      r IN outside[0].rels | 
      CASE 
        WHEN size(labels(startNode(r))) > 1 THEN 
          apoc.coll.removeAll(labels(startNode(r)), ["__Entity__"])[0] + ":" + startNode(r).id + " "
        ELSE 
          startNode(r).id + " "
      END + 
      type(r) + " " +
      CASE 
        WHEN size(labels(endNode(r))) > 1 THEN 
          apoc.coll.removeAll(labels(endNode(r)), ["__Entity__"])[0] + ":" + endNode(r).id
        ELSE 
          endNode(r).id
      END
    ]
  }
} AS text,
score,
{entities: metadata} AS metadata
"""

LOCAL_COMMUNITY_DETAILS_QUERY_PREFIX = """
UNWIND $entityIds as id
MATCH (node) WHERE elementId(node) = id
WITH node, 1.0 as score
"""
LOCAL_COMMUNITY_DETAILS_QUERY_SUFFIX = """
WITH *
UNWIND chunks AS c
MATCH (c)-[:PART_OF]->(d:Document)
RETURN 
    [
        c {
            .*,
            embedding: null,
            fileName: d.fileName,
            fileSource: d.fileSource, 
            element_id: elementId(c)
        }
    ] AS chunks,
    [
        community IN communities WHERE community IS NOT NULL | 
        community {
            .*,
            embedding: null,
            element_id:elementId(community)
        }
    ] AS communities,
    [
        node IN nodes + outside[0].nodes | 
        {
            element_id: elementId(node),
            labels: labels(node),
            properties: {
                id: node.id,
                description: node.description
            }
        }
    ] AS nodes, 
    [
        r IN rels + outside[0].rels | 
        {
            startNode: {
                element_id: elementId(startNode(r)),
                labels: labels(startNode(r)),
                properties: {
                    id: startNode(r).id,
                    description: startNode(r).description
                }
            },
            endNode: {
                element_id: elementId(endNode(r)),
                labels: labels(endNode(r)),
                properties: {
                    id: endNode(r).id,
                    description: endNode(r).description
                }
            },
            relationship: {
                type: type(r),
                element_id: elementId(r)
            }
        }
    ] AS entities
"""

LOCAL_COMMUNITY_SEARCH_QUERY_FORMATTED = LOCAL_COMMUNITY_SEARCH_QUERY.format(
    topChunks=LOCAL_COMMUNITY_TOP_CHUNKS,
    topCommunities=LOCAL_COMMUNITY_TOP_COMMUNITIES,
    topOutsideRels=LOCAL_COMMUNITY_TOP_OUTSIDE_RELS)+LOCAL_COMMUNITY_SEARCH_QUERY_SUFFIX

GLOBAL_SEARCH_TOP_K = 10

GLOBAL_VECTOR_SEARCH_QUERY = """
WITH collect(distinct {community: node, score: score}) AS communities,
     avg(score) AS avg_score

WITH avg_score,
     [c IN communities | c.community.summary] AS texts,
     [c IN communities | {id: elementId(c.community), score: c.score}] AS communityDetails

WITH avg_score, communityDetails,
     apoc.text.join(texts, "\n----\n") AS text

RETURN text,
       avg_score AS score,
       {communitydetails: communityDetails} AS metadata
"""



GLOBAL_COMMUNITY_DETAILS_QUERY = """
MATCH (community:__Community__)
WHERE elementId(community) IN $communityids
WITH collect(distinct community) AS communities
RETURN [community IN communities | 
        community {.*, embedding: null, element_id: elementId(community)}] AS communities
"""

## CHAT MODES 

CHAT_VECTOR_MODE = "vector"
CHAT_FULLTEXT_MODE = "fulltext"
CHAT_ENTITY_VECTOR_MODE = "entity_vector"
CHAT_VECTOR_GRAPH_MODE = "graph_vector"
CHAT_VECTOR_GRAPH_FULLTEXT_MODE = "graph_vector_fulltext"
CHAT_GLOBAL_VECTOR_FULLTEXT_MODE = "global_vector"
CHAT_GRAPH_MODE = "graph"
CHAT_DEFAULT_MODE = "graph_vector_fulltext"

CHAT_MODE_CONFIG_MAP= {
        CHAT_VECTOR_MODE : {
            "retrieval_query": VECTOR_SEARCH_QUERY,
            "top_k": VECTOR_SEARCH_TOP_K,
            "index_name": "vector",
            "keyword_index": None,
            "document_filter": True,
            "node_label": "Chunk",
            "embedding_node_property":"embedding",
            "text_node_properties":["text"],

        },
        CHAT_FULLTEXT_MODE : {
            "retrieval_query": VECTOR_SEARCH_QUERY,  
            "top_k": VECTOR_SEARCH_TOP_K,
            "index_name": "vector",  
            "keyword_index": "keyword", 
            "document_filter": False,            
            "node_label": "Chunk",
            "embedding_node_property":"embedding",
            "text_node_properties":["text"],
        },
        CHAT_ENTITY_VECTOR_MODE : {
            "retrieval_query": LOCAL_COMMUNITY_SEARCH_QUERY_FORMATTED,
            "top_k": LOCAL_COMMUNITY_TOP_K,
            "index_name": "entity_vector",
            "keyword_index": None,
            "document_filter": False,            
            "node_label": "__Entity__",
            "embedding_node_property":"embedding",
            "text_node_properties":["id"],
        },
        CHAT_VECTOR_GRAPH_MODE : {
            "retrieval_query": VECTOR_GRAPH_SEARCH_QUERY,
            "top_k": VECTOR_SEARCH_TOP_K,
            "index_name": "vector",
            "keyword_index": None,
            "document_filter": True,            
            "node_label": "Chunk",
            "embedding_node_property":"embedding",
            "text_node_properties":["text"],
        },
        CHAT_VECTOR_GRAPH_FULLTEXT_MODE : {
            "retrieval_query": VECTOR_GRAPH_SEARCH_QUERY,
            "top_k": VECTOR_SEARCH_TOP_K,
            "index_name": "vector",
            "keyword_index": "keyword",
            "document_filter": False,            
            "node_label": "Chunk",
            "embedding_node_property":"embedding",
            "text_node_properties":["text"],
        },
        CHAT_GLOBAL_VECTOR_FULLTEXT_MODE : {
            "retrieval_query": GLOBAL_VECTOR_SEARCH_QUERY,
            "top_k": GLOBAL_SEARCH_TOP_K,
            "index_name": "community_vector",
            "keyword_index": "community_keyword",
            "document_filter": False,            
            "node_label": "__Community__",
            "embedding_node_property":"embedding",
            "text_node_properties":["summary"],
        },
    }
YOUTUBE_CHUNK_SIZE_SECONDS = 60

QUERY_TO_GET_CHUNKS = """
            MATCH (d:Document)
            WHERE d.fileName = $filename
            WITH d
            OPTIONAL MATCH (d)<-[:PART_OF|FIRST_CHUNK]-(c:Chunk)
            RETURN c.id as id, c.text as text, c.position as position 
            """
            
QUERY_TO_DELETE_EXISTING_ENTITIES = """
                                MATCH (d:Document {fileName:$filename})
                                WITH d
                                MATCH (d)<-[:PART_OF]-(c:Chunk)
                                WITH d,c
                                MATCH (c)-[:HAS_ENTITY]->(e)
                                WHERE NOT EXISTS { (e)<-[:HAS_ENTITY]-()<-[:PART_OF]-(d2:Document) }
                                DETACH DELETE e
                                """   

QUERY_TO_GET_LAST_PROCESSED_CHUNK_POSITION="""
                              MATCH (d:Document)
                              WHERE d.fileName = $filename
                              WITH d
                              MATCH (c:Chunk) WHERE c.embedding is null 
                              RETURN c.id as id,c.position as position 
                              ORDER BY c.position LIMIT 1
                              """   
QUERY_TO_GET_LAST_PROCESSED_CHUNK_WITHOUT_ENTITY = """
                              MATCH (d:Document)
                              WHERE d.fileName = $filename
                              WITH d
                              MATCH (d)<-[:PART_OF]-(c:Chunk) WHERE NOT exists {(c)-[:HAS_ENTITY]->()}
                              RETURN c.id as id,c.position as position 
                              ORDER BY c.position LIMIT 1
                              """
QUERY_TO_GET_NODES_AND_RELATIONS_OF_A_DOCUMENT = """
                              MATCH (d:Document)<-[:PART_OF]-(:Chunk)-[:HAS_ENTITY]->(e) where d.fileName=$filename
                              OPTIONAL MATCH (d)<-[:PART_OF]-(:Chunk)-[:HAS_ENTITY]->(e2:!Chunk)-[rel]-(e)
                              RETURN count(DISTINCT e) as nodes, count(DISTINCT rel) as rels
                              """                              

START_FROM_BEGINNING  = "start_from_beginning"     
DELETE_ENTITIES_AND_START_FROM_BEGINNING = "delete_entities_and_start_from_beginning"
START_FROM_LAST_PROCESSED_POSITION = "start_from_last_processed_position"                                                    

GRAPH_CLEANUP_PROMPT = """
You are tasked with organizing a list of types into semantic categories based on their meanings, including synonyms or morphological similarities. The input will include two separate lists: one for **Node Labels** and one for **Relationship Types**. Follow these rules strictly:
### 1. Input Format
The input will include two keys:
- `nodes`: A list of node labels.
- `relationships`: A list of relationship types.
### 2. Grouping Rules
- Group similar items into **semantic categories** based on their meaning or morphological similarities.
- The name of each category must be chosen from the types in the input list (node labels or relationship types). **Do not create or infer new names for categories**.
- Items that cannot be grouped must remain in their own category.
### 3. Naming Rules
- The category name must reflect the grouped items and must be an existing type in the input list.
- Use a widely applicable type as the category name.
- **Do not introduce new names or types** under any circumstances.
### 4. Output Rules
- Return the output as a JSON object with two keys:
 - `nodes`: A dictionary where each key represents a category name for nodes, and its value is a list of original node labels in that category.
 - `relationships`: A dictionary where each key represents a category name for relationships, and its value is a list of original relationship types in that category.
- Every key and value must come from the provided input lists.
### 5. Examples
#### Example 1:
Input:
{{
 "nodes": ["Person", "Human", "People", "Company", "Organization", "Product"],
 "relationships": ["CREATED_FOR", "CREATED_TO", "CREATED", "PUBLISHED","PUBLISHED_BY", "PUBLISHED_IN", "PUBLISHED_ON"]
}}
Output in JSON:
{{
 "nodes": {{
   "Person": ["Person", "Human", "People"],
   "Organization": ["Company", "Organization"],
   "Product": ["Product"]
 }},
 "relationships": {{
   "CREATED": ["CREATED_FOR", "CREATED_TO", "CREATED"],
   "PUBLISHED": ["PUBLISHED_BY", "PUBLISHED_IN", "PUBLISHED_ON"]
 }}
}}
#### Example 2: Avoid redundant or incorrect grouping
Input:
{{
 "nodes": ["Process", "Process_Step", "Step", "Procedure", "Method", "Natural Process", "Step"],
 "relationships": ["USED_FOR", "USED_BY", "USED_WITH", "USED_IN"]
}}
Output:
{{
 "nodes": {{
   "Process": ["Process", "Process_Step", "Step", "Procedure", "Method", "Natural Process"]
 }},
 "relationships": {{
   "USED": ["USED_FOR", "USED_BY", "USED_WITH", "USED_IN"]
 }}
}}
### 6. Key Rule
If any item cannot be grouped, it must remain in its own category using its original name. Do not repeat values or create incorrect mappings.
Use these rules to group and name categories accurately without introducing errors or new types.
"""

ADDITIONAL_INSTRUCTIONS = """Your goal is to identify and categorize entities while ensuring that specific data 
types such as dates, numbers, revenues, and other non-entity information are not extracted as separate nodes.
Instead, treat these as properties associated with the relevant entities."""

SCHEMA_VISUALIZATION_QUERY = """
CALL db.schema.visualization() YIELD nodes, relationships
RETURN
  [n IN nodes | {
      element_id: elementId(n),
      labels: labels(n),
      properties: apoc.any.properties(n)
  }] AS nodes,
  [r IN relationships | {
      type: type(r),
      properties: apoc.any.properties(r),
      element_id: elementId(r),
      start_node_element_id: elementId(startNode(r)),
      end_node_element_id: elementId(endNode(r))
  }] AS relationships;
"""
