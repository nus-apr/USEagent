import base64
from pathlib import Path

from useagent.common.encoding import is_utf_8_encoded


def test_utf8_file_should_return_true(tmp_path: Path):
    path = tmp_path / "utf8.txt"
    path.write_text("hello ñ", encoding="utf-8")
    assert is_utf_8_encoded(path) is True


def test_chinese_utf8_file_should_return_true(tmp_path: Path):
    path = tmp_path / "chinese.txt"
    path.write_text("你好，世界", encoding="utf-8")
    assert is_utf_8_encoded(path) is True


def test_latin1_file_should_return_false(tmp_path: Path):
    path = tmp_path / "latin1.txt"
    path.write_bytes("Español".encode("latin-1"))
    assert is_utf_8_encoded(path) is False


def test_binary_blob_should_return_false(tmp_path: Path):
    path = tmp_path / "blob.bin"
    path.write_bytes(b"\x00\x01\x02\x03\x04\xff\xfe\xfd")
    assert is_utf_8_encoded(path) is False


def test_png_image_should_return_false(tmp_path: Path):
    path = tmp_path / "image.png"
    base64_png = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
    path.write_bytes(base64.b64decode(base64_png))
    assert is_utf_8_encoded(path) is False
