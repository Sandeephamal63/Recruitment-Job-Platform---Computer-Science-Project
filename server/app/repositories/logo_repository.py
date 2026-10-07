from bson import ObjectId
from gridfs import GridFS
from gridfs.grid_file import GridOut
from pymongo.database import Database


class LogoRepository:
    """GridFS access for employer logo bytes (same database, fs.files/fs.chunks).

    Shares the default GridFS bucket with :class:`CVRepository` — there is no
    named bucket in this project, so a logo is simply another ``fs.files``
    document, distinguished from a CV only by the reference that points at it
    (``users.logoFileRef`` vs ``applications.cvFileRef``).

    The application stores only the GridFS id; the original filename lives in the
    GridFS file's metadata so the public route can restore it.
    """

    def __init__(self, db: Database):
        self._fs = GridFS(db)

    def save(self, content: bytes, filename: str) -> str:
        return str(self._fs.put(content, filename=filename))

    def load(self, file_id: str) -> tuple[bytes, str]:
        grid_file: GridOut = self._fs.get(ObjectId(file_id))
        return grid_file.read(), grid_file.filename or "logo"

    def delete(self, file_id: str) -> None:
        try:
            self._fs.delete(ObjectId(file_id))
        except Exception:
            pass
