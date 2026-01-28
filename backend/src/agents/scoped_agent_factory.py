from typing import Dict, Any, List
from threading import Lock
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import BackgroundTasks

# Services
from src.images.repository.media_item_repository import MediaRepository
from src.images.imagen_service import ImagenService
from src.videos.veo_service import VeoService
from src.audios.audio_service import AudioService
from src.source_assets.repository.source_asset_repository import SourceAssetRepository
from src.brand_guidelines.repository.brand_guideline_repository import BrandGuidelineRepository
from src.common.storage_service import GcsService
from src.auth.iam_signer_credentials_service import IamSignerCredentials
from src.multimodal.gemini_service import GeminiService
from src.common.vector_search_service import VectorSearchService
from src.config.config_service import config_service

# Agents
from src.agents.adk.enforcer import BrandingEnforcerADK
from src.agents.adk.generator import MediaGeneratorADK
from src.agents.adk.poller import JobPollerADK
from src.agents.adk.validator import ValidatorADK
from src.agents.adk.manager import create_media_pipeline

logger = logging.getLogger(__name__)

class ScopedAgentFactory:
    """
    Factory to create ADK agents with dependencies scoped to a specific database session.
    This ensures that background tasks have their own isolated 'World' of services
    and do not rely on potentially closed or shared global state.
    """

    def __init__(
        self,
        # Stateless / Singleton services can be injected once
        vector_search_service: VectorSearchService,
        gemini_service: GeminiService,
        executor: Any,
    ):
        self.vector_search_service = vector_search_service
        self.gemini_service = gemini_service
        self.executor = executor
        # lightweight services that don't hold state can be instantiated here or in create_components
        self.gcs_service = GcsService()
        self.iam_signer = IamSignerCredentials()

    def create_components(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Creates a fresh set of Repositories, Services, and Agents bound to the provided session.
        Returns a dictionary containing the pipeline and individual agents if needed.
        """
        
        # 1. Repositories (Scoped to Session)
        media_repo = MediaRepository(session)
        source_asset_repo = SourceAssetRepository(session)
        brand_guideline_repo = BrandGuidelineRepository(session)

        # 2. Re-instantiate Services with scoped repos
        # Note: We reuse self.gemini_service but if it depended on a closed repo, we'd need to re-create it too.
        # GeminiService takes 'brand_guideline_repo'. If that repo is stateful (db), we MUST re-create GeminiService.
        # Let's check GeminiService __init__.
        # it takes `brand_guideline_repo: BrandGuidelineRepository`. 
        # So YES, we must create a scoped GeminiService to avoid it using a closed DB session for guideline lookups.
        
        scoped_gemini = GeminiService(brand_guideline_repo=brand_guideline_repo)
        
        imagen_service = ImagenService(
            media_repo=media_repo,
            source_asset_repo=source_asset_repo,
            gemini_service=scoped_gemini,
            gcs_service=self.gcs_service,
            iam_signer_credentials=self.iam_signer
        )

        veo_service = VeoService(
            media_repo=media_repo,
            source_asset_repo=source_asset_repo,
            gemini_service=scoped_gemini,
            gcs_service=self.gcs_service,
            iam_signer_credentials=self.iam_signer
        )

        audio_service = AudioService(
             media_repo=media_repo,
             # AudioService might have fewer deps, let's assume standard pattern
             gcs_service=self.gcs_service,
             iam_signer_credentials=self.iam_signer
        )

        # 3. Create Agents
        
        # Enforcer needs VectorSearch (stateless-ish) and Gemini (scoped) and Repo (scoped)
        enforcer = BrandingEnforcerADK(
            name="BrandingEnforcer",
            vector_search_service=self.vector_search_service,
            gemini_service=scoped_gemini,
            brand_guideline_repo=brand_guideline_repo
        )

        generator = MediaGeneratorADK(
            name="MediaGenerator",
            imagen_service=imagen_service,
            veo_service=veo_service,
            audio_service=audio_service,
            executor=self.executor
        )

        poller = JobPollerADK(
            name="JobPoller",
            media_repo=media_repo
        )

        validator = ValidatorADK(
            name="Validator",
            gemini_service=scoped_gemini,
            media_repo=media_repo
        )

        # 4. Pipeline
        pipeline = create_media_pipeline(enforcer, generator, poller, validator)

        return {
            "pipeline": pipeline,
            "enforcer": enforcer,
            "generator": generator,
            "poller": poller,
            "validator": validator,
            "media_repo": media_repo  # Useful for external updates if needed
        }
