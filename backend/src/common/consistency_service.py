import logging
from typing import Callable, Awaitable, TypeVar, Any
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

T = TypeVar("T")

class ConsistencyService:
    """
    Service to handle dual-write consistency between the Database and OpenFGA.
    Implements the "Compensating Transaction" pattern.
    """

    async def perform_dual_write(
        self,
        db_op: Callable[[], Awaitable[T]],
        fga_op: Callable[[T], Awaitable[Any]],
        rollback_op: Callable[[T], Awaitable[Any]],
        error_message: str = "Failed to synchronize permissions."
    ) -> T:
        """
        Executes a database operation and then an FGA operation.
        If FGA fails, rolls back the database operation.

        Args:
            db_op: Async function that performs the DB update and returns the result.
            fga_op: Async function that performs the FGA update. Receives the result of db_op.
            rollback_op: Async function that reverts the DB update if FGA fails. Receives the result of db_op.
            error_message: Error message to display if the operation fails.

        Returns:
            The result of the db_op.
        """
        # 1. Execute DB Operation
        try:
            result = await db_op()
        except Exception as e:
            # If DB fails, just raise. Nothing to rollback yet.
            logger.error(f"DB Operation failed: {e}")
            raise e

        # 2. Execute FGA Operation
        try:
            await fga_op(result)
        except Exception as e:
            logger.error(f"FGA Operation failed: {e}. Initiating rollback...")
            
            # 3. Compensating Transaction (Rollback)
            try:
                await rollback_op(result)
                logger.info("Rollback successful.")
            except Exception as rollback_error:
                # Critical Error: Data is now inconsistent
                logger.critical(f"Rollback FAILED! Data is inconsistent. Error: {rollback_error}")
                # TODO: Alerting / Dead Letter Queue logic could go here
            
            # Raise generic HTTP exception to client
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{error_message} Changes have been reverted."
            )
            
        return result
