import asyncio
import asyncio
import logging
from collections import deque
from typing import Dict, List, AsyncIterator, Optional

# Remove Django-specific imports
from llama_cpp import Llama

from lib.models import Conversation

logger = logging.getLogger(__name__)

ai_models_path = "ai_models"

class LLMModelType:
    DEEPSEEK_R1_DISTILL_LLAMA_8B_Q8_0 = "DeepSeek-R1-Distill-Llama-8B-Q8_0.gguf"


class LLMModelMode:
    LOCAL = "LOCAL"
    REMOTE = "REMOTE"


class LLMInvoker:
    def __init__(self, system_prompt: str, llm_model_type: str, llm: Llama):
        self._system_prompt = system_prompt
        self.llm = llm
        self.llm_model_type = llm_model_type

        self.max_tokens = 4096
        self.max_response_tokens = 1000
        self.system_tokens = self.tokenize_text(self._system_prompt)

    def tokenize_text(self, text: str) -> list:
        return self.llm.tokenize(text.encode("utf-8"))

    def send_message(self, message: str) -> Dict:
        answer = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": message},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return answer

    async def get_conversation_history(self, conversation: Conversation) -> List[Dict[str, str]]:
        messages = sorted(conversation.messages, key=lambda x: x.created_at, reverse=True)
        history = deque()
        total_tokens = self.system_tokens

        for message in messages:
            content = message.content
            msg_tokens = self.tokenize_text(content)

            if len(total_tokens) + len(msg_tokens) + self.max_response_tokens <= self.max_tokens:
                history.appendleft({"role": message.role, "content": content})
                total_tokens += msg_tokens
            else:
                break

        return list(history)

    async def async_send_message_stream(
            self, message: str, conversation: Optional[Conversation] = None
    ) -> AsyncIterator[str]:
        logger.info(f"Starting message stream for: {message}")

        messages = [{"role": "system", "content": self._system_prompt}]
        total_tokens = len(self.system_tokens)

        if conversation:
            history = await self.get_conversation_history(conversation)
            messages.extend(history)
            total_tokens += sum(len(self.tokenize_text(msg["content"])) for msg in history)

        new_message_tokens = len(self.tokenize_text(message))

        # Token management logic
        if total_tokens + new_message_tokens + self.max_response_tokens <= self.max_tokens:
            messages.append({"role": "user", "content": message})
        else:
            while (total_tokens + new_message_tokens + self.max_response_tokens > self.max_tokens
                   and len(messages) > 1):
                removed_message = messages.pop(1)
                total_tokens -= len(self.tokenize_text(removed_message["content"]))
            messages.append({"role": "user", "content": message})

        stream = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=self.max_response_tokens,
            stop=["Human:", "\n\nHuman:"],
            temperature=0.85,
            stream=True,
        )

        for chunk in stream:
            if "choices" in chunk and chunk["choices"]:
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta and delta["content"] is not None:
                    yield delta["content"]
            await asyncio.sleep(0)

        logger.info("Finished streaming message")


class LLMConnect:
    _system_prompt = """You are Sage Browser, an ultra-fast AI assistant..."""  # Your existing prompt

    def __init__(self, system_prompt: Optional[str] = None,
                 model_type: str = LLMModelType.DEEPSEEK_R1_DISTILL_LLAMA_8B_Q8_0):
        self._llm = None
        self.llm_chat = None
        self._system_prompt = system_prompt or self._system_prompt
        self._model = model_type
        self._mode = LLMModelMode.LOCAL
        self.set_llama_model(model_type=self._model)

    def set_llama_model(self, model_type: str):
        model_path = f"{ai_models_path}/{model_type}"
        llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            chat_format="chatml",
            max_tokens=4096,
            temperature=0.95,
            top_p=0.95,
        )
        self._llm = llm
        self.llm_chat = LLMInvoker(
            system_prompt=self._system_prompt,
            llm_model_type=self._model,
            llm=self._llm,
        )


class SingletonLLMConnect:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = LLMConnect(model_type=LLMModelType.DEEPSEEK_R1_DISTILL_LLAMA_8B_Q8_0)
        return cls._instance