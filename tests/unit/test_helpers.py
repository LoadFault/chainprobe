import pytest
from pydantic import ValidationError

from chainprobe.client import decode_u64
from chainprobe.metrics import analyze_heads, percentile
from chainprobe.models import Block

VALID_BLOCK = {
    "number": "0xf8611",
    "hash": "0x" + "ab" * 32,
    "parentHash": "0x" + "cd" * 32,
    "timestamp": "0x6a8d3b44",
}


def test_decode_u64_reads_little_endian():
    assert decode_u64("0x" + (1_790_447_556_000).to_bytes(8, "little").hex()) == 1_790_447_556_000


@pytest.mark.parametrize(("p", "expected"), [(0, 1), (50, 3), (95, 100), (100, 100)])
def test_percentile(p, expected):
    assert percentile([100, 1, 3, 2, 4], p) == expected


def test_block_model_parses_valid_block():
    block = Block.model_validate(VALID_BLOCK)
    assert block.height == 0xF8611


@pytest.mark.parametrize(
    ("field", "value"),
    [("hash", "0x1234"), ("number", "123"), ("parentHash", None)],
    ids=["short-hash", "not-hex", "missing-parent"],
)
def test_block_model_rejects_invalid_fields(field, value):
    with pytest.raises(ValidationError):
        Block.model_validate({**VALID_BLOCK, field: value})


def test_analyze_heads_clean_stream():
    stats = analyze_heads([(0, 1), (6, 2), (12, 3)])
    assert stats.gaps == [] and stats.backwards == []
    assert stats.intervals == [6, 6]


def test_analyze_heads_finds_gap():
    assert analyze_heads([(0, 1), (6, 2), (12, 5)]).gaps == [(2, 5)]


def test_analyze_heads_finds_non_increasing_head():
    assert analyze_heads([(0, 10), (6, 11), (12, 11)]).backwards == [(11, 11)]
