from ...settings import settings


def estimate(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """USD estimate from configs/models.yaml pricing (per million tokens); None if the model is unpriced."""
    price = (settings.models.get("pricing") or {}).get(model)
    if not price or not (input_tokens or output_tokens):
        return None
    return input_tokens / 1e6 * float(price[0]) + output_tokens / 1e6 * float(price[1])
