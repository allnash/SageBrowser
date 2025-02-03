import asyncio
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from lib.models import Conversation, Role


class LLMWorker(QObject):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, llm_client, parent=None):
        super().__init__(parent)
        self.llm_client = llm_client
        self.conversation = Conversation(title="Browser Chat")

    async def process_message(self, message: str):
        try:
            self.conversation.add_message(message, Role.USER)
            complete_response = ""

            async for response_chunk in self.llm_client.llm_chat.async_send_message_stream(
                    message, self.conversation
            ):
                complete_response += response_chunk
                self.response_ready.emit(response_chunk)

            # Add the complete response
            if complete_response:
                self.conversation.add_message(complete_response, Role.ASSISTANT)

        except Exception as e:
            self.error_occurred.emit(f"Error: {str(e)}")


class LLMThread(QThread):
    def __init__(self, worker: LLMWorker, message: str, parent=None):
        super().__init__(parent)
        self.worker = worker
        self.message = message

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.worker.process_message(self.message))
        finally:
            loop.close()


class BrowserLLMIntegration:
    def __init__(self, browser_window, llm_client):
        self.browser = browser_window
        # Set the integration reference in the browser
        self.browser.llm_integration = self
        self.llm_worker = LLMWorker(llm_client)
        self.llm_worker.response_ready.connect(self.handle_llm_response)
        self.llm_worker.error_occurred.connect(self.handle_llm_error)

    def handle_user_message(self, message: str):
        # Create and start LLM thread
        self.llm_thread = LLMThread(self.llm_worker, message)
        self.llm_thread.start()

    def handle_llm_response(self, response: str):
        self.browser.chat_window.add_message(response, False)

    def handle_llm_error(self, error: str):
        self.browser.chat_window.add_message(f"Error: {error}", False)

