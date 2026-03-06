# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uthana import UthanaError, UthanaCharacters, Error, Uthana, detect_mesh_format
from uthana.utils import prepare_video_to_motion
from uthana.models import get_default_ttm_model, get_default_vtm_model


def test_detect_mesh_format_glb(tmp_path: Path) -> None:
    (tmp_path / "x.glb").write_bytes(b"glTF\x02\x00\x00\x00" + b"\x00" * 12)
    assert detect_mesh_format(str(tmp_path / "x.glb")) == "glb"


def test_detect_mesh_format_fbx_binary(tmp_path: Path) -> None:
    (tmp_path / "x.fbx").write_bytes(b"Kaydara FBX Binary  \x00")
    assert detect_mesh_format(str(tmp_path / "x.fbx")) == "fbx"


def test_detect_mesh_format_fbx_ascii(tmp_path: Path) -> None:
    (tmp_path / "x.fbx").write_bytes(b"; FBX 7.4.0 project file")
    assert detect_mesh_format(str(tmp_path / "x.fbx")) == "fbx"


def test_detect_mesh_format_unknown(tmp_path: Path) -> None:
    (tmp_path / "x.obj").write_bytes(b"v 1 2 3")
    assert detect_mesh_format(str(tmp_path / "x.obj")) is None


def test_error_base() -> None:
    err = Error("test message")
    assert str(err) == "test message"
    assert isinstance(err, Exception)


def test_uthana_error() -> None:
    err = UthanaError(404, "Not found")
    assert err.status_code == 404
    assert err.message == "Not found"
    assert "404" in str(err)
    assert "Not found" in str(err)
    assert isinstance(err, Error)


def test_prepare_video_to_motion_supported() -> None:
    variables, filename = prepare_video_to_motion("/tmp/video.mp4", None)
    assert variables["motion_name"] == "video"
    assert filename == "video.mp4"
    assert variables["file"] is None


def test_prepare_video_to_motion_custom_name() -> None:
    variables, filename = prepare_video_to_motion("/tmp/video.mp4", "my_motion")
    assert variables["motion_name"] == "my_motion"
    assert filename == "video.mp4"


def test_prepare_video_to_motion_unsupported_format() -> None:
    with pytest.raises(Error, match="Unsupported video format"):
        prepare_video_to_motion("/tmp/video.mkv", None)


def test_default_characters() -> None:
    assert UthanaCharacters.tar == "cXi2eAP19XwQ"
    assert UthanaCharacters.ava == "cmEE2fT4aSaC"
    assert UthanaCharacters.manny == "c43tbGks3crJ"
    assert UthanaCharacters.quinn == "czCjWEMtWxt8"
    assert UthanaCharacters.y_bot == "cJM4ngRqXg83"


@patch.object(Uthana, "_log_init", return_value={})
@patch("uthana.client.httpx.AsyncClient", return_value=MagicMock())
@patch("uthana.client.httpx.Client", return_value=MagicMock())
def test_motion_url(
    _mock_client: MagicMock,
    _mock_async: MagicMock,
    _mock_log: MagicMock,
) -> None:
    client = Uthana("fake-key")
    url = client._motion_url(
        character_id="char1",
        motion_id="motion1",
        output_format="glb",
        fps=30,
        no_mesh=False,
    )
    assert "char1" in url
    assert "motion1" in url
    assert "glb" in url
    assert "fps=30" in url
    assert "no_mesh=false" in url


def test_get_default_ttm_model() -> None:
    """Default model is loaded from models.ini."""
    model = get_default_ttm_model()
    assert model in ("vqvae-v1", "diffusion-v2", "flow-matching-v1", "nearest-neighbor-v1")


def test_get_default_vtm_model() -> None:
    """Default VTM model is loaded from models.ini."""
    model = get_default_vtm_model()
    assert model in ("video-to-motion-v1", "video-to-motion-v2")


@patch("uthana.client.get_default_ttm_model", return_value="vqvae-v1")
@patch.object(Uthana, "_log_init", return_value={})
@patch("uthana.client.httpx.AsyncClient", return_value=MagicMock())
@patch("uthana.client.httpx.Client", return_value=MagicMock())
def test_ttm_auto_resolves_to_default(
    _mock_client: MagicMock,
    _mock_async: MagicMock,
    _mock_log: MagicMock,
    mock_get_default: MagicMock,
) -> None:
    """When model is 'auto', it resolves to the default from models.ini."""
    client = Uthana("fake-key")
    mutation, variables = client._prepare_and_select_text_to_motion(
        model="auto",
        prompt="a person walking",
        character_id=None,
        foot_ik=None,
        length=None,
        cfg_scale=None,
        seed=None,
        internal_ik=None,
    )
    mock_get_default.assert_called_once()
    assert variables["model"] == "text-to-motion"  # vqvae-v1 uses this


@patch.object(Uthana, "_log_init", return_value={})
@patch("uthana.client.httpx.AsyncClient", return_value=MagicMock())
@patch("uthana.client.httpx.Client", return_value=MagicMock())
def test_motion_url_no_options(
    _mock_client: MagicMock,
    _mock_async: MagicMock,
    _mock_log: MagicMock,
) -> None:
    client = Uthana("fake-key")
    url = client._motion_url(
        character_id="char1",
        motion_id="motion1",
        output_format="fbx",
        fps=None,
        no_mesh=None,
    )
    assert "char1" in url
    assert "motion1" in url
    assert "fbx" in url
    assert "fps=" not in url
    assert "no_mesh=" not in url
