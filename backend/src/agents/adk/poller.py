import logging
import asyncio
from typing import AsyncGenerator, Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.common.schema.media_item_model import JobStatusEnum

logger = logging.getLogger(__name__)

from pydantic import PrivateAttr

class JobPollerADK(BaseAgent):
    """
    ADK Agent solely responsible for polling a job until completion.
    Decouples "Waiting" from "Validating".
    """
    _media_repo: Any = PrivateAttr()
    
    def __init__(self, name: str, media_repo: Any):
        super().__init__(name=name)
        self._media_repo = media_repo
        
    @property
    def media_repo(self):
        return self._media_repo
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        job_id = state.get("job_id")
        
        if not job_id:
             yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Skipping polling: No job_id found.")]))
             return

        logger.info(f"[{self.name}] Polling for Job {job_id}...")
        
        # "Rely on background task":
        # We poll as long as the job is active (PENDING/PROCESSING).
        # We add a generous safety timeout (e.g. 1 hour) just to prevent infinite stuck loops if DB/Worker dies.
        
        import time
        start_time = time.time()
        max_duration_seconds = 3600 # 1 Hour
        
        loops = 0
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_duration_seconds:
                 yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"Polling timed out after {max_duration_seconds}s.")]))
                 return

            job = await self.media_repo.get_by_id(job_id)
            if not job:
                 yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Job not found during polling.")]))
                 return
            
            if job.status == JobStatusEnum.COMPLETED:
                final_job = job
                yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"Job {job_id} COMPLETED.")]))
                break
            
            if job.status == JobStatusEnum.FAILED:
                 error_msg = job.error_message or "Unknown error"
                 yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"Job {job_id} FAILED: {error_msg}")]))
                 return
            
            # Still Processing/Pending
            loops += 1
            
            # Emit heartbeat every ~10s (assuming 2-5s sleep)
            if loops % 5 == 0:
                 yield Event(author=self.name, content=types.Content(parts=[types.Part(text=f"Waiting for generation... ({int(elapsed)}s elapsed)")]))
            
            # Adaptive sleep: 2s fast check, then 5s after 1 minute to save DB ops
            sleep_time = 2 if elapsed < 60 else 5
            await asyncio.sleep(sleep_time)

        # Update state with final assets if found (ensure downstream has fresh data)
        if final_job:
            state["generated_assets"] = [{
                "id": final_job.id,
                "status": final_job.status,
                "gcs_uris": final_job.gcs_uris
            }]
            logger.info(f"[{self.name}] Refreshed state with final assets for Job {job_id}.")
