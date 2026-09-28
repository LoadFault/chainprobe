from typing import Annotated

from pydantic import BaseModel, StringConstraints

Hex = Annotated[str, StringConstraints(pattern=r"^0x[0-9a-fA-F]+$")]
Hash = Annotated[str, StringConstraints(pattern=r"^0x[0-9a-fA-F]{64}$")]


class Block(BaseModel):
    """The part of an eth_getBlockByNumber response the tests rely on."""

    number: Hex
    hash: Hash
    parentHash: Hash
    timestamp: Hex

    @property
    def height(self) -> int:
        return int(self.number, 16)

    @property
    def time(self) -> int:
        return int(self.timestamp, 16)
