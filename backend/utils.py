import base64
import io
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
from typing import List, Tuple

def universal_file_to_cv2_images(file_bytes: bytes, filename: str = "") -> List[np.ndarray]:
    """
    Universally loads ANY file format (PNG, JPG, JPEG, PDF, WEBP, TIFF, BMP, GIF)
    and converts it into a list of OpenCV BGR image arrays (one per page for PDFs).
    """
    images = []

    # Check if PDF file
    is_pdf = filename.lower().endswith(".pdf") or file_bytes.startswith(b"%PDF")

    if is_pdf:
        try:
            pdf = pdfium.PdfDocument(file_bytes)
            for page in pdf:
                # Render page at 2x scale (~300 DPI) for crisp text/OCR
                bitmap = page.render(scale=2.0)
                pil_img = bitmap.to_pil()
                img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                images.append(img_bgr)
            if images:
                return images
        except Exception as e:
            print(f"[PDF Parsing Error] {e}")

    # Process standard and extended image formats via PIL
    try:
        pil_img = Image.open(io.BytesIO(file_bytes))
        # Handle EXIF orientation tag (e.g. photos taken from phone cameras)
        pil_img = ImageOps.exif_transpose(pil_img)
        
        # Handle GIF or multi-frame images
        if getattr(pil_img, "is_animated", False):
            for frame_idx in range(pil_img.n_frames):
                pil_img.seek(frame_idx)
                frame = pil_img.convert("RGB")
                img_bgr = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
                images.append(img_bgr)
            return images

        # Standard single frame image
        # Downscale large mobile phone images (e.g. 4000x3000) to max 1800px for speed & low memory
        max_dim = 1800
        w, h = pil_img.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            pil_img = pil_img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        rgb_img = pil_img.convert("RGB")
        img_bgr = cv2.cvtColor(np.array(rgb_img), cv2.COLOR_RGB2BGR)
        return [img_bgr]
    except Exception as e:
        print(f"[PIL Image Open Error] {e}")

    # Fallback via OpenCV imdecode
    try:
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            h, w = img.shape[:2]
            if max(h, w) > 1800:
                scale = 1800.0 / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            return [img]
    except Exception as e:
        print(f"[OpenCV imdecode Error] {e}")

    return []

def base64_to_cv2(b64_string: str) -> np.ndarray:
    """Decodes base64 string to OpenCV BGR image array."""
    if "," in b64_string:
        b64_string = b64_string.split(",", 1)[1]
    img_bytes = base64.b64decode(b64_string)
    imgs = universal_file_to_cv2_images(img_bytes)
    return imgs[0] if imgs else None

def cv2_to_base64(img: np.ndarray, format: str = "PNG") -> str:
    """Encodes an OpenCV image array to a data URL base64 string."""
    success, buffer = cv2.imencode(f".{format.lower()}", img)
    if not success or buffer is None:
        raise ValueError(f"cv2.imencode failed for format '.{format.lower()}' — image may be empty or corrupted")
    b64_bytes = base64.b64encode(buffer)
    return f"data:image/{format.lower()};base64,{b64_bytes.decode('utf-8')}"

def bytes_to_cv2(img_bytes: bytes, filename: str = "") -> np.ndarray:
    """Decodes raw byte array to an OpenCV image array."""
    imgs = universal_file_to_cv2_images(img_bytes, filename)
    return imgs[0] if imgs else None

def cv2_to_bytes(img: np.ndarray, format: str = "PNG") -> bytes:
    """Encodes OpenCV image array to raw bytes."""
    _, buffer = cv2.imencode(f".{format.lower()}", img)
    return buffer.tobytes()

def deskew_image(img: np.ndarray) -> np.ndarray:
    """Detects rotation skew angle of text/lines and deskews the image."""
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )
        
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 100:
            return img

        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
            
        if abs(angle) < 0.3 or abs(angle) > 45:
            return img
            
        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
        return rotated
    except Exception as e:
        print(f"[Deskew Error] {e}")
        return img

def preprocess_handwritten_image(img: np.ndarray) -> np.ndarray:
    """
    Applies specialized image processing for photos of handwritten numbers on paper.
    Uses CLAHE to eliminate uneven shadows, bilateral filtering for paper grain,
    and adaptive thresholding to bring out pencil/pen ink strokes.
    """
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        equalized = clahe.apply(gray)

        filtered = cv2.bilateralFilter(equalized, d=7, sigmaColor=50, sigmaSpace=50)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        enhanced = cv2.morphologyEx(filtered, cv2.MORPH_CLOSE, kernel)

        return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
    except Exception as e:
        print(f"[Handwritten Preprocessing Error] {e}")
        return img

def preprocess_image(
    img: np.ndarray,
    contrast: float = 1.0,
    brightness: float = 1.0,
    binarize: bool = False,
    auto_deskew: bool = False,
    denoise: bool = False
) -> np.ndarray:
    """Applies configurable image preprocessing pipeline to optimize for OCR."""
    result = img.copy()

    # Always apply handwritten preprocessing (built-in, no toggle needed)
    result = preprocess_handwritten_image(result)

    if auto_deskew:
        result = deskew_image(result)

    if contrast != 1.0 or brightness != 1.0:
        pil_img = Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(pil_img)
            pil_img = enhancer.enhance(contrast)
        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(pil_img)
            pil_img = enhancer.enhance(brightness)
        result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    if denoise:
        result = cv2.fastNlMeansDenoisingColored(result, None, 10, 10, 7, 21)

    if binarize:
        gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        binary = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8
        )
        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    return result

def crop_roi(img: np.ndarray, x: int, y: int, width: int, height: int) -> np.ndarray:
    """Crops a Region of Interest (ROI) from an image."""
    h, w = img.shape[:2]
    x1 = max(0, min(x, w - 1))
    y1 = max(0, min(y, h - 1))
    x2 = max(x1 + 1, min(x + width, w))
    y2 = max(y1 + 1, min(y + height, h))
    return img[y1:y2, x1:x2]

def detect_auto_crop(img: np.ndarray) -> dict:
    """
    Detects the main table grid or section on the page using OpenCV line & contour analysis.
    Returns ROI dict: {"x": int, "y": int, "width": int, "height": int}
    """
    try:
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        
        # Adaptive Thresholding for grid line detection
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 4)
        
        # Detect horizontal grid lines
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 25), 1))
        horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_h)
        
        # Detect vertical grid lines
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(15, h // 25)))
        vertical = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_v)
        
        # Combine grid lines
        table_grid = cv2.add(horizontal, vertical)
        
        # Dilate grid lines to join broken grid cells
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        grid_dilated = cv2.dilate(table_grid, kernel_dilate, iterations=2)
        
        contours, _ = cv2.findContours(grid_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_box = None
        max_area = 0
        
        for cnt in contours:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            # Filter contours that look like table sections (at least 2% of total image area)
            if area > (w * h * 0.02) and bw > (w * 0.2) and bh > 40:
                if area > max_area:
                    max_area = area
                    best_box = {"x": int(bx), "y": int(by), "width": int(bw), "height": int(bh)}
        
        # Fallback to general dark ink / text region contour if explicit grid lines aren't found
        if not best_box:
            kernel_text = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
            text_dilated = cv2.dilate(thresh, kernel_text, iterations=2)
            contours, _ = cv2.findContours(text_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                area = bw * bh
                if area > (w * h * 0.03) and bw > (w * 0.25):
                    if area > max_area:
                        max_area = area
                        best_box = {"x": int(bx), "y": int(by), "width": int(bw), "height": int(bh)}
                        
        if not best_box:
            # Default to full image with 2% margin padding
            best_box = {"x": 0, "y": 0, "width": w, "height": h}
            
        return best_box
    except Exception as e:
        print(f"[Auto Crop Error] {e}")
        return {"x": 0, "y": 0, "width": img.shape[1], "height": img.shape[0]}

