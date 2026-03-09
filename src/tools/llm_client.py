from pathlib import Path
from typing import Any

import yaml
from json_repair import repair_json
from langchain_openai import ChatOpenAI

from .config import load_config
from .prompting import PromptTemplate

PROMPT_DIR = Path(__file__).parent.parent / "prompts"
class LLMClient:
    def __init__(self, model_name: str = "deepseek-chat"):
        self.config = load_config(model_name)
        self.llm = ChatOpenAI(**self.config)

    def _load_prompt(self, prompt_name: str) -> PromptTemplate:
        with open(PROMPT_DIR / f"{prompt_name}.yaml", "r") as f:
            prompt = yaml.safe_load(f)
        prompt = PromptTemplate(**prompt)
        return prompt

    def _render_message(self, prompt: PromptTemplate, **inputs) -> str:
        return prompt.format(**inputs)

    def _handle_structured_response(self, response) -> str:
        return repair_json(response.choices[0].message.content)

    def completion(self, prompt_name: str, temperature: float = 0.7, structured: bool = False, **inputs) -> str:
        prompt = self._load_prompt(prompt_name)
        messages = [
                {"role": "system", "content": self._render_message(prompt=prompt.system, **inputs)},
                {"role": "user", "content": self._render_message(prompt=prompt.user, **inputs)}
        ]

        response = self.llm.invoke(messages)
        return self._handle_structured_response(response) if structured else response.content

if __name__ == "__main__":
    llm_client = LLMClient()
    response = llm_client.completion("hello", structured=False)
    print(response)
