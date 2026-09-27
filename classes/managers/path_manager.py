"""Imports"""
import os
from pathlib import Path


class PathManager:
    @staticmethod
    def exists(path:str) -> bool:
        return os.path.exists(path)

    @staticmethod
    def require_exists(path: str) -> str:
        if not PathManager.exists(path):
            raise FileNotFoundError(f"Path does not exist: {path}")

        return path

    @staticmethod
    def join(*paths) -> str:
        return str(os.path.join(*paths))

    @staticmethod
    def split(path:str) -> list:
        return list(Path(path).parts)
