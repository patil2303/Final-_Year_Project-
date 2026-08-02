import os
import logging
import cv2
import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

class PreprocessingService:
    """
    Service responsible for document image preprocessing.
    Prepares images for OCR by standardizing rotation, contrast, and noise levels.
    """
    
    def __init__(self, processed_folder: str):
        self.processed_folder = processed_folder
        os.makedirs(self.processed_folder, exist_ok=True)
        logger.debug(f"PreprocessingService initialized with folder: {self.processed_folder}")

    def correct_exif_orientation(self, image_path: str) -> Image.Image:
        """
        Loads the image and transposes it according to EXIF orientation metadata.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            A PIL.Image object with corrected orientation.
        """
        logger.debug(f"Applying EXIF correction on image: {image_path}")
        try:
            with Image.open(image_path) as img:
                # Pillow exif_transpose auto-rotates the image based on EXIF tag 274
                transposed_img = ImageOps.exif_transpose(img)
                transposed_img.load()  # Force load pixel data to memory and release file lock
                return transposed_img
        except Exception as e:
            logger.warning(f"EXIF orientation correction failed: {e}")
            # Fallback loader
            fallback_img = Image.open(image_path)
            fallback_img.load()
            return fallback_img

    def pil_to_cv(self, pil_img: Image.Image) -> np.ndarray:
        """Converts a PIL Image to an OpenCV BGR image."""
        img_rgb = np.array(pil_img)
        
        # Handle alpha channel (RGBA to BGR)
        if len(img_rgb.shape) == 3:
            if img_rgb.shape[2] == 4:
                return cv2.cvtColor(img_rgb, cv2.COLOR_RGBA2BGR)
            elif img_rgb.shape[2] == 3:
                return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        
        # Grayscale or fallback copy
        return img_rgb.copy()

    def get_skew_angle(self, cv_img: np.ndarray) -> float:
        """
        Estimates the skew angle of the document.
        
        Args:
            cv_img: OpenCV BGR image.
            
        Returns:
            Skew angle in degrees. Negative for counter-clockwise, positive for clockwise.
        """
        try:
            # 1. Convert to grayscale and blur
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (9, 9), 0)
            
            # 2. Threshold to get binary text (text pixels white, background black)
            thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            
            # 3. Dilate text lines to merge characters horizontally
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
            dilate = cv2.dilate(thresh, kernel, iterations=2)
            
            # 4. Find contours
            contours, _ = cv2.findContours(dilate, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            
            angles = []
            for contour in contours:
                area = cv2.contourArea(contour)
                # Ignore noise contours and extremely large boundaries
                if area < 150 or area > 500000:
                    continue
                
                rect = cv2.minAreaRect(contour)
                angle = rect[-1]
                
                # Normalize angle returned by OpenCV minAreaRect
                width, height = rect[1]
                if width < height:
                    angle = angle - 90
                
                # Check for reasonable skew ranges
                if -45 < angle < 45 and angle != 0:
                    angles.append(angle)
            
            if not angles:
                logger.debug("No significant text deskew angle detected.")
                return 0.0
            
            # Median angle is robust against outlier contours
            median_angle = float(np.median(angles))
            logger.info(f"Detected skew angle: {median_angle:.2f} degrees.")
            return median_angle
        except Exception as e:
            logger.error(f"Error while estimating skew angle: {e}")
            return 0.0

    def rotate_image(self, cv_img: np.ndarray, angle: float) -> np.ndarray:
        """
        Rotates an OpenCV image by a given angle.
        
        Args:
            cv_img: OpenCV image to rotate.
            angle: Angle in degrees to rotate the image.
            
        Returns:
            The rotated OpenCV image.
        """
        if abs(angle) < 0.05:
            return cv_img.copy()
            
        h, w = cv_img.shape[:2]
        center = (w // 2, h // 2)
        
        # Get rotation matrix and warp the affine space
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        # Using INTER_CUBIC for premium interpolation; fill border with replica to avoid black edges
        rotated = cv2.warpAffine(
            cv_img, matrix, (w, h), 
            flags=cv2.INTER_CUBIC, 
            borderMode=cv2.BORDER_REPLICATE
        )
        return rotated

    def improve_contrast_and_grayscale(self, cv_img: np.ndarray) -> np.ndarray:
        """
        Converts the image to grayscale and applies CLAHE for local contrast balancing.
        
        Args:
            cv_img: OpenCV BGR image.
            
        Returns:
            Grayscale image with enhanced local contrast.
        """
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        # CLAHE balances brightness across uneven shadow gradients
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        return enhanced

    def binarize_and_clean(self, gray_img: np.ndarray) -> np.ndarray:
        """
        Applies adaptive thresholding and morphological operations to binarize and clean noise.
        
        Args:
            gray_img: Grayscale OpenCV image.
            
        Returns:
            Binary (black & white) image.
        """
        # Adaptive Gaussian thresholding works best for text documents under uneven lighting
        thresh = cv2.adaptiveThreshold(
            gray_img, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            15, 4
        )
        
        # Morphological operations for small noise cleaning
        # Opening removes small white noise, closing removes small black noise holes in characters
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        
        # We perform opening first to wipe isolated dust pixels
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        return cleaned

    def preprocess_image(self, original_image_path: str) -> dict:
        """
        Executes the full image preprocessing pipeline on an uploaded file.
        
        Args:
            original_image_path: Path to the stored source image.
            
        Returns:
            dict: {
                "processed_image_path": str,
                "width": int,
                "height": int
            }
        """
        if not os.path.exists(original_image_path):
            raise FileNotFoundError(f"Source file not found: {original_image_path}")
            
        logger.info(f"Starting image preprocessing pipeline for: {original_image_path}")
        
        # 1. EXIF Orientation correction
        pil_img = self.correct_exif_orientation(original_image_path)
        
        # 2. Convert to OpenCV
        cv_img = self.pil_to_cv(pil_img)
        
        # 3. Deskewing (Detect skew angle and rotate)
        skew_angle = self.get_skew_angle(cv_img)
        deskewed_img = self.rotate_image(cv_img, skew_angle)
        
        # 4. Grayscale & CLAHE contrast boost
        gray_enhanced = self.improve_contrast_and_grayscale(deskewed_img)
        
        # 5. Adaptive Threshold & Morphological noise removal
        processed_binary = self.binarize_and_clean(gray_enhanced)
        
        # 6. Save preprocessed file
        filename = os.path.basename(original_image_path)
        processed_filename = f"processed_{filename}"
        processed_path = os.path.join(self.processed_folder, processed_filename)
        
        cv2.imwrite(processed_path, processed_binary)
        
        # 7. Get dimensions
        height, width = processed_binary.shape[:2]
        
        logger.info(f"Preprocessing complete. Saved to: {processed_path}. Resolution: {width}x{height}")
        
        return {
            "processed_image_path": os.path.abspath(processed_path),
            "width": width,
            "height": height
        }
