from typing import List, Optional, Dict, Any
from src.common.vector_search_service import VectorSearchService
from src.multimodal.gemini_service import GeminiService
from src.brand_guidelines.repository.brand_guideline_repository import BrandGuidelineRepository

import logging
import json

logger = logging.getLogger(__name__)

def create_search_branding_guidelines_tool(
    vector_search_service: VectorSearchService, 
    gemini_service: GeminiService,
    brand_guideline_repo: BrandGuidelineRepository
):
    """
    Creates a function tool for searching branding guidelines.
    """
    
    async def search_branding_guidelines(query: str, workspace_id: str = "Global") -> Dict[str, Any]:
        """
        Searches for branding guidelines and rules relevant to a query.
        
        Args:
            query (str): The search query.
            workspace_id (str, optional): The ID of the workspace. Defaults to "Global".

        Returns:
            Dict[str, Any]: Contains 'rules_text' (str) and 'reference_image_uris' (List[str]).
        """
        logger.info(f"search_branding_guidelines tool called - Query: {query}, Workspace: {workspace_id}")
        
        # 1. Generate embeddings
        text_query_embedding = vector_search_service.generate_embedding(query, model_type="text")
        multimodal_query_embedding = vector_search_service.generate_embedding(query, model_type="multimodal")
        
        # 1.1 Generate Sparse Embedding
        from src.common.sparse_embedding_service import SparseEmbeddingService
        sparse_service = SparseEmbeddingService()
        sparse_embedding = sparse_service.get_sparse_embedding(query)
        
        if not text_query_embedding and not multimodal_query_embedding:
            return {"rules_text": "Error: Failed to generate embeddings for query.", "reference_image_uris": []}

        # 2. Search
        scope_filter = workspace_id if workspace_id and workspace_id != "Global" else None
        scope_val = None
        if scope_filter:
             try:
                 scope_val = int(scope_filter)
             except ValueError:
                 scope_val = None # Should probably handle error or assume Global?

        try:
             # Use the injected repo!
             active_guideline_ids = await brand_guideline_repo.get_active_guideline_ids(workspace_id=scope_val)
             logger.info(f"search_branding_guidelines - Found {len(active_guideline_ids)} active guidelines for scope {workspace_id}")
        except Exception as e:
            logger.error(f"Failed to fetch active guidelines: {e}")
            active_guideline_ids = []

        if not active_guideline_ids:
            logger.info("search_branding_guidelines - No active guidelines found. Returning empty.")
            return {"rules_text": "No branding guidelines found for this workspace.", "reference_image_uris": []}

        restricts = [
            {"namespace": "scope", "allow_list": [workspace_id or "Global"]},
            {"namespace": "guideline_id", "allow_list": active_guideline_ids}
        ]
        
        search_results = []
        
        # Search Text Index
        if text_query_embedding:
            try:
                text_results = vector_search_service.find_neighbors(
                    query_embedding=text_query_embedding,
                    num_neighbors=5,
                    restricts=restricts,
                    index_type="text",
                    sparse_embedding=sparse_embedding
                )
                logger.info(f"Text index search results: {text_results}")   
                if text_results:
                    search_results.extend(text_results)
            except Exception as e:
                logger.error(f"Text index search failed: {e}")

        # Search Image Index
        if multimodal_query_embedding:
            try:
                image_results = vector_search_service.find_neighbors(
                    query_embedding=multimodal_query_embedding,
                    num_neighbors=3,
                    restricts=restricts,
                    index_type="image",
                    sparse_embedding=sparse_embedding
                )
                logger.info(f"Image index search results: {image_results}")
                if image_results:
                    search_results.extend(image_results)
            except Exception as e:
                logger.error(f"Image index search failed: {e}")
        
        logger.info(f"search_branding_guidelines - Found {len(search_results)} total results")
        
        # 3. Format results
        relevant_text_chunks = []
        relevant_image_uris = []
        guidelines_cache = {}
        
        from src.common.storage_service import GcsService
        gcs_service = GcsService()

        for result in search_results:
            if "_text_" in result.id:
                guideline_id, index_str = result.id.split("_text_")
                type_ = "text"
            elif "_image_" in result.id:
                guideline_id, index_str = result.id.split("_image_")
                type_ = "image"
            else:
                continue
            
            try:
                index = int(index_str)
            except ValueError:
                continue
            
            if guideline_id not in guidelines_cache:
                try:
                    gid_int = int(guideline_id)
                    guideline = await brand_guideline_repo.get_by_id(gid_int)
                    if guideline:
                        guidelines_cache[guideline_id] = guideline
                except ValueError:
                    logger.warning(f"Invalid guideline ID format: {guideline_id}")
                    continue
            
            guideline = guidelines_cache.get(guideline_id)
            if not guideline:
                continue

            if type_ == "text":
                blob_path = f"brand-guidelines/{guideline.workspace_id or 'global'}/processed/{guideline_id}/text/chunk_{index}.json"
                try:
                    full_uri = f"gs://{gcs_service.bucket_name}/{blob_path}"
                    content_bytes = gcs_service.download_bytes_from_gcs(full_uri)
                    if content_bytes:
                        try:
                            chunk_data = json.loads(content_bytes)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to decode JSON from {blob_path}")
                            continue

                        # Robust extraction of text content
                        extracted_parts = []
                        
                        # 1. Standard text fields
                        if chunk_data.get("guideline_text"):
                            extracted_parts.append(chunk_data["guideline_text"])
                        elif chunk_data.get("brand_rules"):
                            rules = chunk_data["brand_rules"]
                            if isinstance(rules, list):
                                extracted_parts.append("\n".join(str(r) for r in rules))
                            elif isinstance(rules, str):
                                extracted_parts.append(rules)
                        
                        # 2. Structured summary fields
                        # Support both CamelCase (from old prompts) and snake_case (from schema/new prompts)
                        name = chunk_data.get("name") or chunk_data.get("brand_name")
                        if name:
                             extracted_parts.append(f"Brand Name: {name}")
                        
                        tov = chunk_data.get("toneOfVoiceSummary") or chunk_data.get("tone_of_voice_summary")
                        if tov:
                            extracted_parts.append(f"Tone of Voice: {tov}")
                            
                        vis = chunk_data.get("visualStyleSummary") or chunk_data.get("visual_style_summary")
                        if vis:
                            extracted_parts.append(f"Visual Style: {vis}")
                            
                        palette = chunk_data.get("colorPalette") or chunk_data.get("color_palette")
                        if palette:
                            if isinstance(palette, list):
                                extracted_parts.append(f"Color Palette: {', '.join(str(c) for c in palette)}")

                        # 3. Fallback: Dump unknown keys if meaningful content is sparse
                        if not extracted_parts:
                             # Try to extract any string values from unknown keys if it looks like a flat dict of info
                             for key, val in chunk_data.items():
                                 if isinstance(val, str) and len(val) > 20 and key not in ["status", "errorMessage"]:
                                     extracted_parts.append(f"{key}: {val}")

                        text = "\n\n".join(extracted_parts)
                        
                        if text:
                            # Apply a reasonable truncation if it's massive, but keep it rich
                            snippet = text[:2000] + "..." if len(text) > 2000 else text
                            relevant_text_chunks.append(f"- [Source: {guideline.name}] {snippet}")
                except Exception as e:
                    logger.error(f"Failed to fetch or process chunk {blob_path}: {e}")

            elif type_ == "image":
                if guideline.reference_image_uris and index < len(guideline.reference_image_uris):
                    uri = guideline.reference_image_uris[index]
                    relevant_image_uris.append(uri)

        if not relevant_text_chunks and not relevant_image_uris:
             return {"rules_text": "No relevant branding rules or images found.", "reference_image_uris": []}

        # 4. Enhance with Guideline Summaries
        # Even if we found specific text chunks, the high-level summaries are critical for the Enforcer.
        # If we found images but no text chunks, these summaries are the ONLY text context we have.
        unique_guidelines = guidelines_cache.values()
        
        response_parts = [] # Initialize here before usage

        if unique_guidelines:
            response_parts.append("\n--- BRAND GUIDELINE SUMMARIES ---")
            for g in unique_guidelines:
                response_parts.append(f"Guideline: {g.name}")
                if g.tone_of_voice_summary:
                    response_parts.append(f"Tone of Voice: {g.tone_of_voice_summary}")
                if g.visual_style_summary:
                    response_parts.append(f"Visual Style: {g.visual_style_summary}")
            response_parts.append("-----------------------------------")

        if not relevant_text_chunks and not unique_guidelines:
             return {"rules_text": "No relevant branding rules or images found.", "reference_image_uris": []}

        if relevant_text_chunks:
            response_parts.append("\n--- RELEVANT TEXT EXCERPTS ---")
            response_parts.extend(relevant_text_chunks)
        
        # We NO LONGER return text representation of images in 'rules_text' as it is redundant
        # and not useful for the text-only Enforcer Agent.
        # The 'reference_image_uris' list is passed separately to the generation model.

        return {
            "rules_text": "\n".join(response_parts),
            "reference_image_uris": relevant_image_uris
        }

    return search_branding_guidelines



def create_fetch_guideline_tool(brand_guideline_repo: BrandGuidelineRepository):
    """
    Creates a function tool for fetching full branding guideline details.
    """
    async def fetch_full_guideline(guideline_id: str) -> str:
        """Retrieves full guideline."""
        logger.info(f"fetch_full_guideline tool called - ID: {guideline_id}")
        
        try:
            guideline = await brand_guideline_repo.get_by_id(int(guideline_id))
            if not guideline:
                return f"Error: Guideline with ID {guideline_id} not found."
                
            details = [
                f"Guideline: {guideline.name}",
                f"Tone of Voice: {guideline.tone_of_voice_summary or 'N/A'}",
                f"Visual Style: {guideline.visual_style_summary or 'N/A'}",
                f"Full Text: {guideline.guideline_text or 'N/A'}",
                f"Reference Images: {', '.join(guideline.reference_image_uris) if guideline.reference_image_uris else 'None'}"
            ]
            return "\n\n".join(details)
            
        except Exception as e:
            logger.error(f"Failed to fetch guideline {guideline_id}: {e}")
            return f"Error fetching guideline: {str(e)}"

    return fetch_full_guideline
