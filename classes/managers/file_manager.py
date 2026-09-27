"""Imports"""
import inspect
import os
import shutil

from classes.managers.folder_manager import FolderManager
from classes.managers.path_manager import PathManager

"""Functions"""
def _notify_not_implemented():
    raise NotImplementedError(f"{inspect.currentframe().f_back.f_code.co_name}() not currently implemented")

class FileManager:

    """Helper Methods"""
    @staticmethod
    def get_extension(name:str) -> str:
        """
        Returns the file extension
        :param name: File name
        :return: The file's extension
        """
        return name.split(".")[-1].lower()
    """File Specific Method Path Preparation"""
    @staticmethod
    def _prepare_path_for_create(file_name: str,
                                 file_path: str) -> str:
        """
        Creates and necessary subfolders and joins the paths
        :param file_name: The file name
        :param file_path: The file path
        :return: The joined path
        """
        # Creates any subfolders that don't already exist
        FolderManager.create_folders_along_path(file_path)

        # Build the full file path
        final_path = PathManager.join(file_path, file_name)

        return final_path
    @staticmethod
    def _prepare_path_for_open(file_name: str,
                               file_path: str) -> str:
        """
        Creates the full path and checks if the path exists
        :param file_name:
        :param file_path:
        :return: The full path
        """
        # Build the full file path
        final_path = PathManager.join(file_path, file_name)

        #Checks if the path exists
        PathManager.require_exists(final_path)

        return final_path
    @staticmethod
    def _prepare_path_for_copy(source_path: str,
                               destination_path: str,
                               source_name: str | None,
                               destination_name:str|None) -> tuple[str, str]:
        # Creates folders that don't exist for new destination
        FolderManager.create_folders_along_path(destination_path)

        #Creates the full source path
        if source_name is None:
            final_source_path = source_path
        else:
            final_source_path = PathManager.join(source_path, source_name)

        #Creates the full destination path
        if destination_name is None:
            final_destination_path = destination_path
        else:
            final_destination_path = PathManager.join(destination_path, destination_name)

        return final_source_path, final_destination_path

    """File Specific Methods"""
    @staticmethod
    def get_files_at_location(path: str) -> list[str]:
        """Return sorted file names in a folder, excluding subfolders.

        Only the immediate folder is searched. Raises FileNotFoundError
        if the path is missing and NotADirectoryError if it is not a folder.
        """
        with os.scandir(path) as entries:
            return sorted(entry.name for entry in entries if entry.is_file())

    @staticmethod
    def delete(path: str) -> None:
        """Permanently delete a file, raising FileNotFoundError if missing."""
        os.remove(path)

    @classmethod
    def copy(cls, source_path: str,
             destination_path: str,
             source_name: str | None = None,
             destination_name: str | None = None) -> str:
        #Prepare the copy path
        final_source_path,final_destination_path = cls._prepare_path_for_copy(source_path = source_path,
                                                                              destination_path = destination_path,
                                                                              source_name = source_name,
                                                                              destination_name = destination_name)
        #Does the copying
        shutil.copy2(final_source_path, final_destination_path)

        return final_destination_path

    # noinspection PyTypeChecker
    @classmethod
    def create(cls, name:str,
               path:str,
               content = None) -> str:
        _notify_not_implemented()

    @classmethod
    def open(cls,
             name:str,
             path:str):
        _notify_not_implemented()

