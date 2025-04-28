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
        self.auto_fill_requested = False

    def handle_user_message(self, message: str):
        """Process user messages and handle form fill requests"""
        # Check if this is a request to fill a form
        form_fill_phrases = [
            "fill the form", "fill this form", "fill out the form", "fill out this form",
            "complete the form", "complete this form", "autofill", "auto fill",
            "fill with sample data", "fill with test data", "generate form data"
        ]

        is_form_fill_request = any(phrase in message.lower() for phrase in form_fill_phrases)

        if is_form_fill_request:
            # Use the auto_fill command instead of directly calling detect_form_fields
            self.browser.chat_window.add_message("I'll help you fill out this form with sample data.", Role.ASSISTANT)
            self.browser.handle_browser_command("auto_fill", {})
        else:
            # Regular LLM processing for other messages
            self.llm_thread = LLMThread(self.llm_worker, message)
            self.llm_thread.start()

    def handle_llm_error(self, error: str):
        self.browser.chat_window.add_message(f"Error: {error}", Role.ASSISTANT)

    def generate_sample_form_data(self, fields, auto_fill=True):
        """Generate sample data for form fields"""
        # Only process if we have fields
        if not fields:
            self.browser.chat_window.add_message("No form fields to fill", Role.ASSISTANT)
            return

        # Format field information for the LLM
        field_descriptions = []
        for field in fields:
            field_desc = f"- {field.get('label') or field.get('name') or field.get('id')}"
            field_desc += f" (Type: {field.get('type')})"

            if field.get('required'):
                field_desc += " [Required]"

            if field.get('options') and len(field.get('options')) > 0:
                options_str = ", ".join([opt.get('text') for opt in field.get('options')])
                field_desc += f" [Options: {options_str}]"

            if field.get('radioOptions') and len(field.get('radioOptions')) > 0:
                options_str = ", ".join([opt.get('text') for opt in field.get('radioOptions')])
                field_desc += f" [Options: {options_str}]"

            field_descriptions.append(field_desc)

        field_info = "\n".join(field_descriptions)

        # Create a prompt for the LLM
        prompt = f"""Please generate realistic sample data for the following form fields. 
The data should be appropriate for each field type and label. Return the result in JSON format 
with each field having a key-value pair where the key is the field identifier (label, name, or id)
and the value is the sample data. For select, radio, or checkbox fields, ensure the value is one 
of the available options.

Form fields:
{field_info}

Respond with JSON data only, no explanations. Example format:
{{
  "First Name": "John",
  "Last Name": "Smith",
  "Email": "john.smith@example.com"
}}
"""

        # Store auto_fill flag for later use in handle_llm_response
        if auto_fill:
            self.browser.chat_window.add_message("🤖 Generating realistic sample data to auto-fill the form...",
                                                 Role.ASSISTANT)
            self.auto_fill_requested = True
        else:
            self.auto_fill_requested = False

        # Start LLM thread
        self.llm_thread = LLMThread(self.llm_worker, prompt)
        self.llm_thread.start()

    def handle_llm_response(self, response: str):
        """Handle LLM responses with direct form filling for JSON data"""
        self.browser.chat_window.add_message(response, False)

        # Check if the response appears to be JSON
        if response.strip().startswith('{') and response.strip().endswith('}'):
            try:
                import json
                import re

                # Extract JSON from response
                json_pattern = r'({.*})'
                json_match = re.search(json_pattern, response, re.DOTALL)

                if json_match:
                    json_str = json_match.group(1)
                    generated_data = json.loads(json_str)

                    # Format for display
                    formatted_data = json.dumps(generated_data, indent=2)

                    # Check if this was an auto_fill request
                    if hasattr(self, 'auto_fill_requested') and self.auto_fill_requested:
                        # Reset the flag
                        self.auto_fill_requested = False

                        # Display intent to fill the form
                        self.browser.chat_window.add_message(
                            f"✨ Auto-filling form with generated data...",
                            False
                        )

                        # Directly call the fillform command with the generated data
                        self.browser.handle_browser_command("fillform", {"data": generated_data})
                    else:
                        # Just display the generated data without filling
                        self.browser.chat_window.add_message(
                            f"Generated form data:\n```json\n{formatted_data}\n```",
                            False
                        )
            except Exception as e:
                self.browser.chat_window.add_message(f"Error processing form data: {str(e)}", False)