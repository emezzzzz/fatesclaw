from __future__ import annotations

import unittest

from fatesclaw_dashboard.state import AppState, ViewName


class AppStateStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_spoken_stream_merges_and_commits(self) -> None:
        state = AppState()

        await state.update_spoken("hola", role="assistant", streaming=True)
        await state.update_spoken("hola mundo", role="assistant", streaming=False)

        snap = await state.snapshot()
        self.assertEqual(snap.live_spoken, "hola mundo")
        self.assertEqual(len(snap.chats), 1)
        self.assertEqual(snap.chats[0].text, "hola mundo")

    async def test_thinking_stream_merges_and_commits(self) -> None:
        state = AppState()

        await state.update_thinking("analizando", streaming=True)
        await state.update_thinking("analizando contexto", streaming=False)

        snap = await state.snapshot()
        self.assertEqual(snap.live_thinking, "analizando contexto")
        self.assertEqual(len(snap.thoughts), 1)
        self.assertEqual(snap.thoughts[0].text, "analizando contexto")

    async def test_completed_assistant_messages_do_not_merge_together(self) -> None:
        state = AppState()
        await state.add_chat(role="assistant", text="first reply", streaming=False)
        await state.add_chat(role="assistant", text="second reply", streaming=False)

        snap = await state.snapshot()
        self.assertEqual(len(snap.chats), 2)
        self.assertEqual(snap.chats[0].text, "first reply")
        self.assertEqual(snap.chats[1].text, "second reply")
        self.assertEqual(snap.live_spoken, "second reply")

    async def test_completed_thought_messages_do_not_merge_together(self) -> None:
        state = AppState()
        await state.update_thinking("first thought", streaming=False)
        await state.update_thinking("second thought", streaming=False)

        snap = await state.snapshot()
        self.assertEqual(len(snap.thoughts), 2)
        self.assertEqual(snap.thoughts[0].text, "first thought")
        self.assertEqual(snap.thoughts[1].text, "second thought")
        self.assertEqual(snap.live_thinking, "second thought")

    async def test_agent_streams_are_isolated_and_switchable(self) -> None:
        state = AppState()
        await state.set_available_agents(["alpha", "main"])

        await state.update_spoken("hello main", role="assistant", streaming=False, agent="main")
        await state.update_thinking("main thinks", streaming=False, agent="main")

        await state.update_spoken("hello alpha", role="assistant", streaming=False, agent="alpha")
        await state.update_thinking("alpha thinks", streaming=False, agent="alpha")

        snap = await state.snapshot()
        self.assertEqual(snap.selected_agent, "alpha")
        self.assertEqual(snap.live_spoken, "hello alpha")
        self.assertEqual(snap.live_thinking, "alpha thinks")

        switched = await state.select_agent("main")
        self.assertTrue(switched)
        snap = await state.snapshot()
        self.assertEqual(snap.selected_agent, "main")
        self.assertEqual(snap.live_spoken, "hello main")
        self.assertEqual(snap.live_thinking, "main thinks")

    async def test_chat_input_draft_is_per_agent(self) -> None:
        state = AppState()
        await state.set_available_agents(["alpha", "main"])

        await state.append_chat_input("hello", agent="main")
        await state.append_chat_input("hello alpha", agent="alpha")

        snap = await state.snapshot()
        self.assertEqual(snap.selected_agent, "alpha")
        self.assertEqual(snap.chat_input_draft, "hello alpha")

        await state.select_agent("main")
        snap = await state.snapshot()
        self.assertEqual(snap.chat_input_draft, "hello")

    async def test_chat_cursor_follows_latest_message(self) -> None:
        state = AppState()
        await state.update_spoken("line one", role="assistant", streaming=False)
        await state.update_spoken("line two", role="assistant", streaming=False)

        snap = await state.snapshot()
        self.assertEqual(len(snap.chats), 2)
        self.assertEqual(snap.view_cursors[ViewName.CHAT].selected_index, 1)

    async def test_mind_cursor_follows_latest_thought(self) -> None:
        state = AppState()
        await state.update_thinking("idea one", streaming=False)
        await state.update_thinking("idea two", streaming=False)

        snap = await state.snapshot()
        self.assertEqual(len(snap.thoughts), 2)
        self.assertEqual(snap.view_cursors[ViewName.MIND].selected_index, 1)


if __name__ == "__main__":
    unittest.main()
