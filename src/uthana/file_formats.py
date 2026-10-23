"""Format hints from upload bytes; callers must still validate the content."""

FORMAT_SIGNATURES = (
    (b"glTF", "glb"),
    (b"Kaydara FBX Binary", "fbx"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8", "jpg"),
    (b"\x1aE\xdf\xa3", "webm"),
)
VIDEO_HEADER_BYTES = 64
MESH_HEADER_BYTES = 20


def detect_file_format(data: bytes) -> str | None:
    """Return an upload format hint without a leading dot, or None if unknown.

    Recognizes GLB, FBX, PNG, JPEG, WebP, WebM, MP4/MOV containers and JSON
    candidates for GLTF. Signatures do not prove a file is valid or safe. MOV
    and MP4 share container markers and return the common hint ``mp4``.
    """
    if detected := next(
        (name for signature, name in FORMAT_SIGNATURES if data.startswith(signature)), None
    ):
        return detected
    stripped = data.lstrip()
    if stripped.startswith(b"; FBX"):
        return "fbx"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    if any(atom in data[:VIDEO_HEADER_BYTES] for atom in (b"ftyp", b"moov", b"mdat")):
        return "mp4"
    if stripped.startswith(b"{"):
        return "gltf"
    return None
