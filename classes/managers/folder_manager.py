"""Imports"""
import os
import shutil

from classes.managers.path_manager import PathManager


class FolderManager:
    @staticmethod
    def create(name:str,
               path:str|None = None) -> str:
        """
        Creates a new folder
        :param name: Folder name
        :param path: Base folder path
        :return: The new folder path
        """
        #Joins the path if need be
        if name is None:
            final_path = path
        else:
            final_path = os.path.join(path, name)

        #Creates a new folder if it doesn't already exist
        os.makedirs(final_path, exist_ok = True)

        return final_path

    @staticmethod
    def delete(path:str) -> None:
        """Permanently delete a folder and all its contents.

        Raises FileNotFoundError if the folder does not exist.
        Raises NotADirectoryError if the path points to a file.
        """
        shutil.rmtree(path)

    @staticmethod
    def zip(path:str) -> str:
        """Zip a folder's contents beside it and return the archive path.

        For example, 'assets/receipts' creates 'assets/receipts.zip'.
        An existing archive is overwritten; the source folder is retained.
        """
        folder_path = os.path.abspath(path)
        if not os.path.isdir(folder_path):
            raise NotADirectoryError(f"Folder does not exist: {path}")

        return shutil.make_archive(
            base_name=folder_path,
            format="zip",
            root_dir=folder_path
        )

    @staticmethod
    def unzip(path: str, destination_path: str | None = None) -> str:
        """Extract a ZIP and return the absolute destination folder path.

        By default, 'assets/receipts.zip' extracts into 'assets/receipts'.
        Existing files may be overwritten; the ZIP file is retained.
        """
        archive_path = os.path.abspath(path)
        if destination_path is None:
            destination_path = os.path.splitext(archive_path)[0]
        destination_path = os.path.abspath(destination_path)

        FolderManager.create_folders_along_path(destination_path)

        shutil.unpack_archive(archive_path, destination_path, format="zip")
        return destination_path

    @staticmethod
    def create_folders_along_path(path:str) -> None:
        # Creates any subfolders that don't already exist
        folders = PathManager.split(path)
        base_path = ""

        for folder in folders:
            #Creates the new base path
            base_path = PathManager.join(base_path, folder)

            #Checks if that path already exists
            if not PathManager.exists(base_path):
                #Creates a new folder
                FolderManager.create(name = folder,
                                     path = path)




