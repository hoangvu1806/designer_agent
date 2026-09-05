import asyncio
from pathlib import Path

from app.models import OpenPencilProfile, RunCreate, RunStage, RunStatus
from app.store import Store


def test_session_and_run_round_trip(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = Store(tmp_path / "test.db")
        await store.initialize()
        session = await store.create_session("Landing page")
        run = await store.create_run(
            session.id,
            RunCreate(
                prompt="Create a calm commerce landing page",
                screen_name="Home",
                mcp_profile={
                    "endpoint": "http://127.0.0.1:7600/mcp",
                    "source_file": "system.fig",
                    "output_file": "generated/home.fig",
                },
            ),
        )

        restored = await store.get_run(run.id)

        assert restored is not None
        assert restored.screen_name == "Home"
        assert restored.library_ids == []
        assert restored.mcp_profile is not None
        assert restored.mcp_profile.output_file == f"generated/{run.id}/Home.fig"
        updated = await store.update_mcp_profile(
            run.id,
            OpenPencilProfile(
                endpoint="http://127.0.0.1:7600/mcp",
                source_file="new-system.fig",
                output_file="generated/retry.fig",
            ),
        )
        assert updated.mcp_profile
        assert updated.mcp_profile.source_file == "new-system.fig"
        assert updated.mcp_profile.output_file == f"generated/{run.id}/Home.fig"
        await store.update_run(
            run.id,
            stage=RunStage.FINISHED,
            status=RunStatus.COMPLETED,
            intent="chat",
            assistant_message="Xin chào!",
        )
        answered = await store.get_run(run.id)
        assert answered and answered.intent == "chat"
        assert answered.assistant_message == "Xin chào!"

        duplicate = await store.create_run(
            session.id,
            RunCreate(
                prompt="Create another calm commerce landing page",
                screen_name="Home.fig",
                mcp_profile={
                    "endpoint": "http://127.0.0.1:7600/mcp",
                    "source_file": "system.fig",
                },
            ),
        )
        assert duplicate.mcp_profile
        assert duplicate.mcp_profile.output_file == f"generated/{duplicate.id}/Home.fig"
        assert duplicate.mcp_profile.output_file != restored.mcp_profile.output_file

    asyncio.run(scenario())
