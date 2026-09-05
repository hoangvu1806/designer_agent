from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


class PromptLibrary:
    def __init__(self, directory: Path = PROMPT_DIR) -> None:
        self.directory = directory
        self._cache: dict[str, str] = {}

    def render(self, name: str, **values: object) -> str:
        template = self._load(name)
        for key, value in values.items():
            template = template.replace("{{" + key + "}}", str(value))
        return template

    def _load(self, name: str) -> str:
        if name not in self._cache:
            path = self.directory / f"{name}.md"
            self._cache[name] = path.read_text(encoding="utf-8")
        return self._cache[name]
