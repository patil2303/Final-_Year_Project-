from abc import ABC, abstractmethod
import logging
try:
    from models.extraction_result import ExtractionResult, AnswerItem
except ImportError:
    class AnswerItem:
        def __init__(self, **kwargs): self.__dict__.update(kwargs)
    class ExtractionResult:
        def __init__(self, **kwargs): self.__dict__.update(kwargs)

logger = logging.getLogger(__name__)

class BaseOCRService(ABC):
    """
    Abstract Base Class for OCR extraction services.
    Inherit from this class when implementing actual AI OCR services.
    """
    
    @abstractmethod
    def extract_information(self, file_path: str) -> ExtractionResult:
        """
        Extracts information from an answer sheet image.
        
        Args:
            file_path: Absolute path to the saved image file.
            
        Returns:
            An ExtractionResult domain object.
        """
        pass


class MockOCRService(BaseOCRService):
    """
    A mock OCR service returning sample parsed data.
    Used for testing routes and client integrations prior to OCR implementation.
    """
    
    def extract_information(self, file_path: str) -> ExtractionResult:
        logger.info(f"[MockOCRService] Extracting info from file: {file_path}")
        
        # Simulating standard extraction results for demonstration
        answers = [
            AnswerItem(question_number="1", extracted_answer="A", confidence=0.98, score=1.0, max_score=1.0),
            AnswerItem(question_number="2", extracted_answer="C", confidence=0.95, score=1.0, max_score=1.0),
            AnswerItem(question_number="3", extracted_answer="B", confidence=0.45, score=0.0, max_score=1.0, remarks="Low confidence"),
            AnswerItem(question_number="4", extracted_answer="D", confidence=0.89, score=1.0, max_score=1.0),
            AnswerItem(question_number="5", extracted_answer="A", confidence=0.92, score=0.0, max_score=1.0)
        ]
        
        result = ExtractionResult(
            student_id="STU10293",
            student_id_confidence=0.97,
            exam_code="MATH-101",
            total_score=3.0,
            max_total_score=5.0,
            answers=answers,
            raw_ocr_text="STUDENT ID: STU10293\nEXAM CODE: MATH-101\n1. A\n2. C\n3. B\n4. D\n5. A",
            metadata={"processed_by": "MockOCRService", "file_path": file_path}
        )
        
        return result
