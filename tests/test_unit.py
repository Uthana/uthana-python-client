# (c) Copyright 2026 Uthana, Inc. All Rights Reserved

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uthana import Error, Uthana, UthanaCharacters, UthanaError, detect_mesh_format
from uthana.models import models
from uthana.utils import prepare_create_character, prepare_video_to_motion


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


def test_prepare_create_character_glb(tmp_path: Path) -> None:
    path = tmp_path / "model.glb"
    path.write_bytes(b"glTF\x02\x00\x00\x00" + b"\x00" * 12)
    variables, name, ext, filename = prepare_create_character(
        str(path), auto_rig=True, front_facing=False
    )
    assert variables["name"] == "model"
    assert variables["auto_rig"] is True
    assert variables["auto_rig_front_facing"] is False
    assert name == "model"
    assert ext == "glb"
    assert filename == "model.glb"


def test_prepare_create_character_fallback_ext(tmp_path: Path) -> None:
    path = tmp_path / "model.xyz"
    path.write_bytes(b"unknown format")
    variables, name, ext, _ = prepare_create_character(str(path), None, None)
    assert ext == "xyz"


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


def test_models_ttm_default() -> None:
    """Default TTM model is loaded from models.ini."""
    assert models.ttm.default in models.ttm.models


def test_models_vtm_default() -> None:
    """Default VTM model is loaded from models.ini."""
    assert models.vtm.default in models.vtm.models


@patch.object(models.ttm, "default", "vqvae-v1")
@patch.object(Uthana, "_log_init", return_value={})
@patch("uthana.client.httpx.AsyncClient", return_value=MagicMock())
@patch("uthana.client.httpx.Client", return_value=MagicMock())
def test_ttm_auto_resolves_to_default(
    _mock_client: MagicMock,
    _mock_async: MagicMock,
    _mock_log: MagicMock,
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
    assert variables["model"] == "text-to-motion"  # vqvae-v1 uses this


@patch.object(Uthana, "_log_init", return_value={})
@patch("uthana.client.httpx.AsyncClient", return_value=MagicMock())
@patch("uthana.client.httpx.Client", return_value=MagicMock())
def test_ttm_diffusion_v2_variables(
    _mock_client: MagicMock,
    _mock_async: MagicMock,
    _mock_log: MagicMock,
) -> None:
    """Diffusion-v2 model produces correct variables."""
    client = Uthana("fake-key")
    mutation, variables = client._prepare_and_select_text_to_motion(
        model="diffusion-v2",
        prompt="dancing",
        character_id=None,
        foot_ik=None,
        length=5.0,
        cfg_scale=7.5,
        seed=42,
        internal_ik=True,
    )
    assert variables["model"] == "text-to-motion-bucmd"
    assert variables["prompt"] == "dancing"
    assert variables["length"] == 5.0
    assert variables["cfg_scale"] == 7.5
    assert variables["seed"] == 42
    assert variables["retargeting_ik"] is True


@patch.object(Uthana, "_log_init", return_value={})
@patch("uthana.client.httpx.AsyncClient", return_value=MagicMock())
@patch("uthana.client.httpx.Client", return_value=MagicMock())
def test_ttm_unknown_model_raises(
    _mock_client: MagicMock,
    _mock_async: MagicMock,
    _mock_log: MagicMock,
) -> None:
    """Unknown model raises ValueError."""
    client = Uthana("fake-key")
    with pytest.raises(ValueError, match="Unknown model"):
        client._prepare_and_select_text_to_motion(
            model="invalid-model",  # type: ignore[arg-type]
            prompt="walk",
            character_id=None,
            foot_ik=None,
            length=None,
            cfg_scale=None,
            seed=None,
            internal_ik=None,
        )


@patch.object(Uthana, "_log_init", return_value={})
@patch("uthana.client.httpx.AsyncClient", return_value=MagicMock())
@patch("uthana.client.httpx.Client", return_value=MagicMock())
def test_build_character_output(
    _mock_client: MagicMock,
    _mock_async: MagicMock,
    _mock_log: MagicMock,
) -> None:
    """_build_character_output parses response correctly."""
    client = Uthana("fake-key")
    result = {
        "data": {
            "create_character": {
                "character": {"id": "char123"},
                "auto_rig_confidence": 0.85,
            }
        }
    }
    output = client._build_character_output(result=result, ext="glb")
    assert output.character_id == "char123"
    assert output.auto_rig_confidence == 0.85
    assert "char123" in output.url
    assert output.url.endswith(".glb")


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
