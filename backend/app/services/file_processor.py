"""Service for processing uploaded files (PDF, DOCX) and extracting text content."""

import os
from pathlib import Path
from typing import Tuple
import PyPDF2
import docx


class FileProcessor:
    """Process uploaded files and extract text content."""

    ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt'}

    @staticmethod
    def validate_file(filename: str, file_size: int, max_size: int = 10 * 1024 * 1024) -> Tuple[bool, str]:
        """
        Validate file extension and size.

        Args:
            filename: Original filename
            file_size: Size of file in bytes
            max_size: Maximum allowed size in bytes (default 10MB)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check extension
        ext = Path(filename).suffix.lower()
        if ext not in FileProcessor.ALLOWED_EXTENSIONS:
            return False, f"File type {ext} not allowed. Allowed types: {', '.join(FileProcessor.ALLOWED_EXTENSIONS)}"

        # Check size
        if file_size > max_size:
            max_mb = max_size / (1024 * 1024)
            return False, f"File size exceeds maximum of {max_mb:.1f}MB"

        return True, ""

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """
        Extract text content from PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text content
        """
        try:
            text_content = []

            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)

                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text_content.append(page.extract_text())

            return "\n\n".join(text_content)

        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")

    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """
        Extract text content from DOCX file.

        Args:
            file_path: Path to DOCX file

        Returns:
            Extracted text content
        """
        try:
            doc = docx.Document(file_path)

            text_content = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)

            return "\n\n".join(text_content)

        except Exception as e:
            raise Exception(f"Error extracting text from DOCX: {str(e)}")

    @staticmethod
    def extract_text_from_txt(file_path: str) -> str:
        """
        Extract text content from TXT file.

        Args:
            file_path: Path to TXT file

        Returns:
            File content
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            with open(file_path, 'r', encoding='latin-1') as file:
                return file.read()
        except Exception as e:
            raise Exception(f"Error reading text file: {str(e)}")

    @staticmethod
    def process_file(file_path: str) -> str:
        """
        Process file and extract text content based on file type.

        Args:
            file_path: Path to file

        Returns:
            Extracted text content
        """
        ext = Path(file_path).suffix.lower()

        if ext == '.pdf':
            return FileProcessor.extract_text_from_pdf(file_path)
        elif ext in ['.docx', '.doc']:
            return FileProcessor.extract_text_from_docx(file_path)
        elif ext == '.txt':
            return FileProcessor.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal attacks.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Get just the filename, no path components
        filename = os.path.basename(filename)

        # Remove any dangerous characters
        dangerous_chars = ['..', '/', '\\', '\0']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')

        return filename
