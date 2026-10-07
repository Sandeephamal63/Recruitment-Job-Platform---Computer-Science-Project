from bson import ObjectId
from gridfs import GridFS
from gridfs.grid_file import GridOut
from pymongo.database import Database


class AvatarRepository:
    """GridFS access for candidate profile-avatar bytes (fs.files/fs.chunks).

    Shares the default GridFS bucket with :class:`CVRepository` and
    :class:`LogoRepository` — there is no named bucket in this project, so an
    avatar is simply another ``fs.files`` document, distinguished by the
    reference that points at it (``users.avatarFileRef``).

    Kept as its own class rather than reusing ``LogoRepository`` so the
    repository a service is handed says what it stores, and so the two can
    diverge without touching logo behaviour.
    """

    def __init__(self, db: Database):
        self._fs = GridFS(db)

    def save(self, content: bytes, filename: str) -> str:
        return str(self._fs.put(content, filename=filename))

    def load(self, file_id: str) -> tuple[bytes, str]:
        grid_file: GridOut = self._fs.get(ObjectId(file_id))
        return grid_file.read(), grid_file.filename or "avatar"

    def delete(self, file_id: str) -> None:
        try:
            self._fs.delete(ObjectId(file_id))
        except Exception:
            pass
