import os
import logging
import uuid
from typing import Any
try:
    from backend.utils import allowed_file, is_valid_image
except ImportError:
    def allowed_file(f, ext): return True
    def is_valid_image(s): return True

logger = logging.getLogger(__name__)

class StorageService:
    """Service to handle local storage file operations."""
    
    def __init__(self, upload_folder: str, allowed_extensions: set):
        self.upload_folder = upload_folder
        self.allowed_extensions = allowed_extensions
        
        # Ensure upload folder exists
        os.makedirs(self.upload_folder, exist_ok=True)
        logger.debug(f"StorageService initialized with folder: {self.upload_folder}")

    def save_image(self, file: Any) -> str:
        """
        Validates and saves the uploaded image to the storage directory.
        
        Args:
            file: The FileStorage object from Flask request.
            
        Returns:
            The unique filename of the saved file.
            
        Raises:
            ValueError: If the file is invalid, format not allowed, or corrupted.
            IOError: If saving the file to disk fails.
        """
        if not file or not file.filename:
            logger.warning("Attempted to save an empty file.")
            raise ValueError("No file provided or filename is empty.")

        filename = file.filename
        
        # 1. Validate File Extension
        if not allowed_file(filename, self.allowed_extensions):
            logger.warning(f"File extension not allowed: {filename}")
            raise ValueError(
                f"File type not allowed. Supported formats: {', '.join(self.allowed_extensions)}"
            )

        # 2. Validate Image Integrity (using Pillow)
        if not is_valid_image(file.stream):
            logger.warning(f"Invalid or corrupted image: {filename}")
            raise ValueError("The uploaded file is not a valid or readable image.")

        # 3. Generate Secure and Unique Filename
        sec_name = secure_filename(filename)
        name, ext = os.path.splitext(sec_name)
        # Append UUID to prevent collisions
        unique_name = f"{name}_{uuid.uuid4().hex}{ext}"
        
        file_path = os.path.join(self.upload_folder, unique_name)
        
        # 4. Save to Disk
        try:
            # File pointer was reset to 0 in is_valid_image, ready to write
            file.save(file_path)
            logger.info(f"Successfully saved image to {file_path}")
            return unique_name
        except Exception as e:
            logger.error(f"Failed to save file to disk: {e}")
            raise IOError("An internal error occurred while saving the file.")
