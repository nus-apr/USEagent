from pathlib import Path


def is_utf_8_encoded(path: Path) -> bool:
    # DevNote:
    # We can see issues if the file tries to be opened with utf-8 but it's e.g. an image or just spanish.
    # This is more common than you would think, because some projects have translation files.
    try:
        with open(path, "rb") as f:
            for line in f:
                line.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False
