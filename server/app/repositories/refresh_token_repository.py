from typing import Any

from pymongo.database import Database


class RefreshTokenRepository:
    """The ``refreshTokens`` collection (auth infrastructure): opaque token
    records keyed by a random tokenId, bcrypt-hashed secret, user, expiry."""

    def __init__(self, db: Database):
        self._collection = db.refreshTokens

    def create(self, document: dict) -> str:
        return str(self._collection.insert_one(document).inserted_id)

    def find_by_token_id(self, token_id: str) -> dict | None:
        return self._collection.find_one({"tokenId": token_id})

    def delete_by_token_id(self, token_id: str) -> None:
        self._collection.delete_one({"tokenId": token_id})

    def delete_by_id(self, token_id: Any) -> None:
        self._collection.delete_one({"_id": token_id})