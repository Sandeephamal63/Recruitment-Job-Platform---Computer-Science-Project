from gridfs import GridFS
from gridfs.grid_file import GridOut
from bson import ObjectId
from pymongo.database import Database


class CVRepository:
    """GridFS access for original CV bytes (same database, fs.files/fs.chunks).

    The application stores only the GridFS id (``cvFileRef``); original filename
    lives in the GridFS file's metadata so downloads can restore it.
    """

    def __init__(self, db: Database):
        self._fs = GridFS(db)

    def save(self, content: bytes, filename: str) -> str:
        return str(self._fs.put(content, filename=filename))

    def load(self, file_id: str) -> tuple[bytes, str]:
        grid_file: GridOut = self._fs.get(ObjectId(file_id))
        return grid_file.read(), grid_file.filename or "cv"

    def filenames_by_ids(self, file_ids: list[ObjectId]) -> dict[str, str]:
        if not file_ids:
            return {}
        return {str(f._id): f.filename or "cv" for f in self._fs.find({"_id": {"$in": file_ids}})}

    def delete(self, file_id: str) -> None:
        try:
            self._fs.delete(ObjectId(file_id))
        except Exception:
            pass