from pathlib import Path


class OrionModel:
    def predict(self, rows):
        return ["ReleaseHold" for _ in rows]


def restore():
    Path("orion-deserialization-canary").write_text("bounded isolated effect")
    return OrionModel()
