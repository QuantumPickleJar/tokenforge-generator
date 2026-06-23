"""Exercise Tokenforge's AI candidate/composition contracts without ComfyUI or a GPU."""

from __future__ import annotations

from PIL import Image, ImageDraw

from tokenforge_local.ai_composition import apply_protected_overlay
from tokenforge_local.ai_models import AIEditRequest, AIEditResult


class FakeAIBackend:
    """Dry-run backend useful for validating the candidate-only integration."""

    endpoint = "fake://local"

    def test_connection(self) -> str:
        return "Fake local AI backend connected."

    def edit_image(self, request: AIEditRequest) -> AIEditResult:
        image = Image.open(request.image_path).convert("RGB")
        return AIEditResult(image=image)


def main() -> None:
    base = Image.new("RGB", (64, 48), "steelblue")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle((4, 4, 30, 14), fill=(255, 255, 255, 255))
    result = apply_protected_overlay(base, overlay)
    assert result.getpixel((5, 5)) == (255, 255, 255)
    print("AI smoke passed: fake candidate flow and protected overlay need no ComfyUI/GPU.")


if __name__ == "__main__":
    main()
