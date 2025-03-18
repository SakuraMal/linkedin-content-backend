import os
import magic
import logging
from typing import List, Tuple, Dict, Any
from werkzeug.datastructures import FileStorage

class FileValidator:
    """
    Service for validating uploaded files against constraints.
    
    This service checks files for:
    - Maximum number of files
    - Maximum file size
    - Allowed file types (MIME types)
    - File content validation
    """
    
    def __init__(self, 
                 max_files: int = 3, 
                 max_file_size: int = 2 * 1024 * 1024,  # 2MB
                 allowed_types: List[str] = None):
        """
        Initialize the file validator with constraints.
        
        Args:
            max_files: Maximum number of files allowed
            max_file_size: Maximum size per file in bytes
            allowed_types: List of allowed MIME types
        """
        self.max_files = max_files
        self.max_file_size = max_file_size
        self.allowed_types = allowed_types or ['image/jpeg', 'image/png', 'image/jpg']
        self.logger = logging.getLogger(__name__)
        
    def validate_files(self, files: List[FileStorage]) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate uploaded files against constraints.
        
        Args:
            files: List of file objects to validate
            
        Returns:
            Tuple[bool, Dict]: (is_valid, validation_result)
        """
        self.logger.info(f"Validating {len(files)} files")
        
        if not files:
            self.logger.warning("No files provided for validation")
            return False, {"error": "No files provided"}
            
        if len(files) > self.max_files:
            self.logger.warning(f"Too many files: {len(files)}. Maximum allowed: {self.max_files}")
            return False, {"error": f"Too many files. Maximum allowed: {self.max_files}"}
        
        total_size = 0
        validation_errors = []
        
        for file in files:
            # Check file size
            file_size = file.content_length or 0
            if file_size == 0:
                # If content_length is not available, try to get the size by reading the file
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)  # Reset file pointer
                
            if file_size > self.max_file_size:
                error_msg = f"File {file.filename} exceeds maximum size of {self.max_file_size / (1024 * 1024)}MB"
                self.logger.warning(error_msg)
                validation_errors.append(error_msg)
            
            total_size += file_size
            
            # Check file type using python-magic
            try:
                file_content = file.read(2048)  # Read first 2KB for MIME detection
                file.seek(0)  # Reset file pointer
                
                mime_type = magic.from_buffer(file_content, mime=True)
                if mime_type not in self.allowed_types:
                    error_msg = f"File {file.filename} has unsupported type: {mime_type}"
                    self.logger.warning(error_msg)
                    validation_errors.append(error_msg)
                    
                # Additional security checks
                self._check_file_content_safety(file, file_content, mime_type, validation_errors)
                
            except Exception as e:
                error_msg = f"Error validating file {file.filename}: {str(e)}"
                self.logger.error(error_msg)
                validation_errors.append(error_msg)
            
        if total_size > (self.max_files * self.max_file_size):
            error_msg = f"Total upload size exceeds maximum of {self.max_files * self.max_file_size / (1024 * 1024)}MB"
            self.logger.warning(error_msg)
            validation_errors.append(error_msg)
            
        if validation_errors:
            return False, {"error": validation_errors}
            
        self.logger.info("Files validated successfully")
        return True, {"message": "Files validated successfully"}
    
    def _check_file_content_safety(self, file: FileStorage, content: bytes, mime_type: str, errors: List[str]) -> None:
        """
        Perform additional safety checks on file content.
        
        Args:
            file: The file object
            content: The first few bytes of the file
            mime_type: The detected MIME type
            errors: List to append errors to
        """
        # Check for empty files
        if len(content) == 0:
            errors.append(f"File {file.filename} is empty")
            return
            
        # For images, check for valid image headers
        if mime_type.startswith('image/'):
            # JPEG signature check
            if mime_type == 'image/jpeg' and not (content.startswith(b'\xff\xd8\xff') or content.startswith(b'\xff\xd8')):
                errors.append(f"File {file.filename} has invalid JPEG signature")
                
            # PNG signature check
            elif mime_type == 'image/png' and not content.startswith(b'\x89PNG\r\n\x1a\n'):
                errors.append(f"File {file.filename} has invalid PNG signature")
                
        # Additional checks could be added here for other file types
        # For example, checking for executable content, scripts, etc.
        
    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename to prevent path traversal and other attacks.
        
        Args:
            filename: The original filename
            
        Returns:
            str: Sanitized filename
        """
        # Remove any directory paths
        filename = os.path.basename(filename)
        
        # Remove any potentially dangerous characters
        # Keep only alphanumeric, dash, underscore, and dot
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
        filename = ''.join(c for c in filename if c in safe_chars)
        
        # Ensure the filename is not empty
        if not filename:
            filename = "unnamed_file"
            
        return filename 