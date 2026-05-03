from rate_card.hashing import content_hash


def _model(key: str, price: float) -> dict[str, object]:
    return {
        "key": key,
        "provider": "openai",
        "model_id": key.split(":")[-1],
        "mode": "chat",
        "input_per_million": price,
        "output_per_million": price * 4,
        "context_window": 128000,
        "capabilities": [],
        "verified": "2026-05-02",
        "sources": ["litellm"],
    }


def test_hash_starts_with_sha256() -> None:
    result = content_hash([_model("openai:gpt-4o", 2.5)])
    assert result.startswith("sha256:")
    assert len(result) == 71


def test_same_input_same_hash() -> None:
    models = [_model("openai:gpt-4o", 2.5), _model("anthropic:claude-3-haiku", 0.25)]
    assert content_hash(models) == content_hash(models)


def test_reordered_keys_same_hash() -> None:
    a = {"key": "openai:gpt-4o", "input_per_million": 2.5, "output_per_million": 10.0}
    b = {"output_per_million": 10.0, "key": "openai:gpt-4o", "input_per_million": 2.5}
    assert content_hash([a]) == content_hash([b])


def test_price_change_different_hash() -> None:
    original = [_model("openai:gpt-4o", 2.5)]
    changed = [_model("openai:gpt-4o", 3.0)]
    assert content_hash(original) != content_hash(changed)


def test_added_model_different_hash() -> None:
    one = [_model("openai:gpt-4o", 2.5)]
    two = [_model("openai:gpt-4o", 2.5), _model("anthropic:claude-3-haiku", 0.25)]
    assert content_hash(one) != content_hash(two)


def test_empty_list() -> None:
    result = content_hash([])
    assert result.startswith("sha256:")


def test_modality_pricing_order_independent() -> None:
    # modality keys in different insertion order must produce the same hash
    a = {
        **_model("openai:gpt-rt", 4.0),
        "modality_pricing": {
            "audio": {"input_per_million": 32.0},
            "image": {"input_per_million": 5.0},
        },
    }
    b = {
        **_model("openai:gpt-rt", 4.0),
        "modality_pricing": {
            "image": {"input_per_million": 5.0},
            "audio": {"input_per_million": 32.0},
        },
    }
    assert content_hash([a]) == content_hash([b])
