import os
import json
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class LayoutDetectionService:
    """
    Service responsible for detecting the page boundaries, aligning/normalizing
    the image to a standard template size, and retrieving configured Regions of Interest (ROIs).
    """

    def __init__(self, template_config_path: str, processed_folder: str):
        self.template_config_path = template_config_path
        self.processed_folder = processed_folder
        self.template_name = ""
        self.target_width = 1000
        self.target_height = 1400
        self.rois = {}

        # Ensure folders exist
        os.makedirs(self.processed_folder, exist_ok=True)
        
        # Load ROI template configuration
        self._load_template()
        
        # Force target dimensions to exactly 1400x2000 pixels
        self.target_width = 1400
        self.target_height = 2000

    def _load_template(self):
        """Loads target size and ROI coordinates from the template configuration file."""
        if not os.path.exists(self.template_config_path):
            raise FileNotFoundError(f"Template configuration file not found: {self.template_config_path}")
        
        try:
            with open(self.template_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            self.template_name = config.get("template_name", "unknown")
            self.target_width = config.get("target_width", 1000)
            self.target_height = config.get("target_height", 1400)
            self.rois = config.get("rois", {})
            logger.info(f"Loaded layout template '{self.template_name}' ({self.target_width}x{self.target_height}) successfully.")
        except Exception as e:
            logger.error(f"Failed to parse template JSON: {e}")
            raise

    def _four_point_transform(self, image: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """
        Applies a perspective warp to obtain a top-down birds-eye view of the image.
        
        Args:
            image: Source OpenCV image.
            pts: Array of 4 corner coordinates [[x,y], ...].
            
        Returns:
            The warped top-down document image.
        """
        # Sort points by their x-coordinate
        pts_sorted_x = pts[np.argsort(pts[:, 0]), :]
        
        # Grab the two left-most and two right-most points
        left_most = pts_sorted_x[:2, :]
        right_most = pts_sorted_x[2:, :]
        
        # Sort the left-most coordinates vertically (smallest y is top-left, largest y is bottom-left)
        left_most_sorted = left_most[np.argsort(left_most[:, 1]), :]
        (tl, bl) = left_most_sorted
        
        # Sort the right-most coordinates vertically (smallest y is top-right, largest y is bottom-right)
        right_most_sorted = right_most[np.argsort(right_most[:, 1]), :]
        (tr, br) = right_most_sorted
        
        rect = np.array([tl, tr, br, bl], dtype="float32")
        
        # Check validity to avoid collapsing perspective
        for i in range(4):
            for j in range(i + 1, 4):
                if np.linalg.norm(rect[i] - rect[j]) < 100:
                    raise ValueError("Collapsed or extremely narrow quadrilateral detected.")
        
        # Compute edge lengths
        top_len = np.linalg.norm(tr - tl)
        bottom_len = np.linalg.norm(br - bl)
        left_len = np.linalg.norm(bl - tl)
        right_len = np.linalg.norm(br - tr)
        
        if top_len == 0 or bottom_len == 0 or left_len == 0 or right_len == 0:
            raise ValueError("Zero-length edge detected.")
            
        # Verify symmetry of opposite sides
        if not (0.65 < top_len / bottom_len < 1.5) or not (0.65 < left_len / right_len < 1.5):
            raise ValueError("Highly asymmetric page boundary contour.")
            
        (tl, tr, br, bl) = rect
        
        # Compute maximum width
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        # Compute maximum height
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        if maxWidth == 0 or maxHeight == 0:
            raise ValueError("Zero dimensions warped image.")
            
        # Verify aspect ratio of the warped quadrilateral is reasonable for a page (A4/Letter is ~0.7-0.8)
        aspect = maxWidth / maxHeight
        if not (0.4 < aspect < 1.3):
            raise ValueError(f"Invalid page aspect ratio: {aspect:.2f}")
            
        # Construct destination points for flat top-down projection
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")
        
        # Calculate warp matrix and warp perspective
        matrix = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, matrix, (maxWidth, maxHeight))
        return warped

    def detect_and_normalize_page(self, cv_img: np.ndarray, original_img: np.ndarray = None) -> np.ndarray:
        """
        Detects document border contours, performs perspective warp, and scales.
        Then, registers the perspective warped page against the reference template using ORB features.
        Saves visual debugging images to backend/debug/registration/ and enforces a Quality Gate.
        
        Args:
            cv_img: Source OpenCV image (binary/gray or BGR).
            original_img: Optional original color image to apply warping directly on.
            
        Returns:
            Normalized OpenCV image of size (1400, 2000) in color.
        """
        # Ensure backend debug directories exist
        debug_dir = os.path.abspath(os.path.join(self.processed_folder, "..", "debug"))
        debug_reg_dir = os.path.join(debug_dir, "registration")
        os.makedirs(debug_reg_dir, exist_ok=True)
        
        # Save original color image
        source_color = original_img if original_img is not None else cv_img.copy()
        cv2.imwrite(os.path.join(debug_reg_dir, "original.jpg"), source_color)
        
        # Define paths for template image
        backend_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        template_dir = os.path.join(backend_dir, "template")
        template_path = os.path.join(template_dir, "acpce_template.jpg")
        
        # Step 1: Detect page contour and perform perspective warp
        page_contour = None
        try:
            h, w = cv_img.shape[:2]
            img_area = h * w
            
            if len(cv_img.shape) == 3:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = cv_img.copy()
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Threshold-based contour detection
            _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
            
            for contour in contours:
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
                if len(approx) == 4 and cv2.contourArea(contour) > 0.15 * img_area:
                    temp_rect = approx.reshape(4, 2)
                    pts_sorted_x = temp_rect[np.argsort(temp_rect[:, 0]), :]
                    left_most = pts_sorted_x[:2, :]
                    right_most = pts_sorted_x[2:, :]
                    left_most_sorted = left_most[np.argsort(left_most[:, 1]), :]
                    right_most_sorted = right_most[np.argsort(right_most[:, 1]), :]
                    tl, bl = left_most_sorted
                    tr, br = right_most_sorted
                    test_rect = np.array([tl, tr, br, bl], dtype="float32")
                    
                    valid = True
                    for i in range(4):
                        for j in range(i + 1, 4):
                            if np.linalg.norm(test_rect[i] - test_rect[j]) < 100:
                                valid = False
                    if valid:
                        page_contour = approx
                        break
                        
            # Fallback to Canny contour detection if needed
            if page_contour is None:
                edged = cv2.Canny(blur, 75, 200)
                contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
                for contour in contours:
                    peri = cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
                    if len(approx) == 4 and cv2.contourArea(contour) > 0.15 * img_area:
                        temp_rect = approx.reshape(4, 2)
                        pts_sorted_x = temp_rect[np.argsort(temp_rect[:, 0]), :]
                        left_most = pts_sorted_x[:2, :]
                        right_most = pts_sorted_x[2:, :]
                        left_most_sorted = left_most[np.argsort(left_most[:, 1]), :]
                        right_most_sorted = right_most[np.argsort(right_most[:, 1]), :]
                        tl, bl = left_most_sorted
                        tr, br = right_most_sorted
                        test_rect = np.array([tl, tr, br, bl], dtype="float32")
                        
                        valid = True
                        for i in range(4):
                            for j in range(i + 1, 4):
                                if np.linalg.norm(test_rect[i] - test_rect[j]) < 100:
                                    valid = False
                        if valid:
                            page_contour = approx
                            break
        except Exception as e:
            logger.error(f"Error during page contour detection: {e}")
            
        # Draw detected contour on original.jpg equivalent and save to detected_page.jpg
        contour_img = source_color.copy()
        if page_contour is not None:
            cv2.drawContours(contour_img, [page_contour], -1, (0, 255, 0), 3)
        cv2.imwrite(os.path.join(debug_reg_dir, "detected_page.jpg"), contour_img)
        
        # Warp color image directly
        if page_contour is not None:
            try:
                warped = self._four_point_transform(source_color, page_contour.reshape(4, 2))
                logger.info("Quad page contour detected. Normalizing via perspective warp.")
            except Exception as e:
                logger.warning(f"Perspective transform failed, falling back to scale resizing: {e}")
                warped = source_color.copy()
        else:
            logger.info("No quad page contour found. Falling back to scale resizing.")
            warped = source_color.copy()
            
        # Resize to target size (1400x2000) for perspective_corrected image
        corrected = cv2.resize(warped, (self.target_width, self.target_height))
        cv2.imwrite(os.path.join(debug_reg_dir, "perspective_corrected.jpg"), corrected)
        
        # Step 2: Register corrected page against the template
        if not os.path.exists(template_path):
            logger.warning(f"Reference template image not found at {template_path}. Skipping registration and using corrected page.")
            # Save fallback debug images
            cv2.imwrite(os.path.join(debug_reg_dir, "registered_page.jpg"), corrected)
            cv2.imwrite(os.path.join(debug_reg_dir, "registration_overlay.jpg"), corrected)
            cv2.imwrite(os.path.join(debug_dir, "normalized_page.jpg"), corrected)
            
            # Print fallback dimensions as expected
            print(f"Original image dimensions: {source_color.shape[1]}x{source_color.shape[0]}")
            print(f"Warped page dimensions: {warped.shape[1]}x{warped.shape[0]}")
            print(f"Normalized page dimensions: {corrected.shape[1]}x{corrected.shape[0]}")
            return corrected
            
        tpl = cv2.imread(template_path)
        if tpl is None:
            raise ValueError(f"Failed to read reference template image from {template_path}")
            
        tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
        corrected_gray = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY)
        
        # Feature detection and matching using ORB
        orb = cv2.ORB_create(nfeatures=2000)
        kp_tpl, des_tpl = orb.detectAndCompute(tpl_gray, None)
        kp_corr, des_corr = orb.detectAndCompute(corrected_gray, None)
        
        if len(kp_corr) < 500:
            logger.info("Corrected page has very few features (possibly a dummy or blank page). Skipping registration.")
            cv2.imwrite(os.path.join(debug_reg_dir, "registered_page.jpg"), corrected)
            cv2.imwrite(os.path.join(debug_reg_dir, "registration_overlay.jpg"), corrected)
            cv2.imwrite(os.path.join(debug_dir, "normalized_page.jpg"), corrected)
            
            # Print fallback dimensions
            print(f"Original image dimensions: {source_color.shape[1]}x{source_color.shape[0]}")
            print(f"Warped page dimensions: {warped.shape[1]}x{warped.shape[0]}")
            print(f"Normalized page dimensions: {corrected.shape[1]}x{corrected.shape[0]}")
            return corrected
            
        if des_tpl is None or des_corr is None:
            logger.warning("Descriptors could not be computed. Registration failed.")
            raise ValueError("Registration failed.")
            
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des_tpl, des_corr)
        matches = sorted(matches, key=lambda x: x.distance)
        
        # Select top matches
        good_matches = matches[:150]
        if len(good_matches) < 10:
            logger.warning(f"Fewer than 10 matches found ({len(good_matches)}). Registration failed.")
            raise ValueError("Registration failed.")
            
        src_pts = np.float32([kp_tpl[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp_corr[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        H, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
        
        if H is None:
            logger.warning("Homography matrix estimation failed. Registration failed.")
            raise ValueError("Registration failed.")
            
        # Warp the corrected image using estimated Homography to template coordinate space
        registered = cv2.warpPerspective(corrected, H, (tpl.shape[1], tpl.shape[0]))
        
        # Calculate registration metrics
        scale_x = np.sqrt(H[0, 0]**2 + H[1, 0]**2)
        scale_y = np.sqrt(H[0, 1]**2 + H[1, 1]**2)
        scale = (scale_x + scale_y) / 2.0
        
        angle_rad = np.arctan2(H[1, 0], H[0, 0])
        angle_deg = angle_rad * 180.0 / np.pi
        
        tx = H[0, 2]
        ty = H[1, 2]
        
        # Calculate Reprojection RMSE
        transformed_pts = cv2.perspectiveTransform(dst_pts, H)
        inliers_transformed = transformed_pts[mask.ravel() == 1]
        inliers_src = src_pts[mask.ravel() == 1]
        
        if len(inliers_src) == 0:
            logger.warning("No RANSAC inliers found. Registration failed.")
            raise ValueError("Registration failed.")
            
        rmse = np.sqrt(np.mean(np.sum((inliers_transformed - inliers_src) ** 2, axis=-1)))
        
        # Print metrics to console in specified format
        print("\nRotation:")
        print(f"{angle_deg:.1f}°")
        print("\nScale:")
        print(f"{scale:.3f}")
        print("\nTranslation:")
        print(f"x={int(round(tx))}")
        print(f"y={int(round(ty))}")
        print("\nHomography matrix:")
        print(H)
        print("\nRegistration RMSE:")
        print(f"{rmse:.1f} px")
        
        # Enforce Quality Gate (RMSE <= 5.0 px)
        if rmse > 5.0:
            logger.warning(f"Registration failed: RMSE {rmse:.2f} px exceeds Quality Gate threshold of 5.0 px.")
            raise ValueError("Registration failed.")
            
        # Save Debug Images
        # 4. feature_matches.jpg (draw matched keypoints)
        matches_img = cv2.drawMatches(tpl, kp_tpl, corrected, kp_corr, good_matches, None, flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        cv2.imwrite(os.path.join(debug_reg_dir, "feature_matches.jpg"), matches_img)
        
        # 5. registered_page.jpg
        cv2.imwrite(os.path.join(debug_reg_dir, "registered_page.jpg"), registered)
        
        # 6. registration_overlay.jpg (blend template and registered with alpha=0.5)
        overlay = cv2.addWeighted(tpl, 0.5, registered, 0.5, 0)
        cv2.imwrite(os.path.join(debug_reg_dir, "registration_overlay.jpg"), overlay)
        
        # Save exact registered page as normalized_page.jpg to debug dir for downstream services
        cv2.imwrite(os.path.join(debug_dir, "normalized_page.jpg"), registered)
        
        # Also print original/warped/normalized dimensions for compatibility
        print(f"Original image dimensions: {source_color.shape[1]}x{source_color.shape[0]}")
        print(f"Warped page dimensions: {warped.shape[1]}x{warped.shape[0]}")
        print(f"Normalized page dimensions: {registered.shape[1]}x{registered.shape[0]}")
        
        return registered

    def process_layout(self, image_path: str) -> dict:
        """
        Runs the full page normalization pipeline, saves the aligned page,
        and returns the mapped ROIs dictionary structure.
        
        Args:
            image_path: Absolute path to the preprocessed binary image.
            
        Returns:
            dict: {
                "normalized_image_path": str,
                "rois": {
                    "student_name": [x, y, w, h],
                    ...
                }
            }
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found for layout detection: {image_path}")

        logger.info(f"Running layout detection for image: {image_path}")
        cv_img = cv2.imread(image_path)
        if cv_img is None:
            raise ValueError(f"Failed to read image as cv2 matrix: {image_path}")

        # Try to resolve original color image from uploads folder
        filename = os.path.basename(image_path).replace("processed_", "")
        uploads_dir = os.path.abspath(os.path.join(self.processed_folder, "..", "uploads"))
        original_path = os.path.join(uploads_dir, filename)
        
        original_img = None
        if os.path.exists(original_path):
            original_img = cv2.imread(original_path)
            if original_img is not None:
                logger.info(f"Loaded original color image: {original_path} (shape: {original_img.shape})")

        # 1. Geometry Normalization (Perspective Warp or Resize)
        normalized_img = self.detect_and_normalize_page(cv_img, original_img)

        # 2. Save Normalized Image
        filename = os.path.basename(image_path)
        normalized_filename = f"normalized_{filename}"
        normalized_path = os.path.join(self.processed_folder, normalized_filename)
        cv2.imwrite(normalized_path, normalized_img)
        logger.info(f"Saved normalized sheet to: {normalized_path}")

        # 3. Calculate absolute coordinates from percentage-based template config
        h_norm, w_norm = normalized_img.shape[:2]
        absolute_rois = {}
        for name, pct_box in self.rois.items():
            x_pct, y_pct, w_pct, h_pct = pct_box
            x_abs = int((x_pct / 100.0) * w_norm)
            y_abs = int((y_pct / 100.0) * h_norm)
            w_abs = int((w_pct / 100.0) * w_norm)
            h_abs = int((h_pct / 100.0) * h_norm)
            absolute_rois[name] = [x_abs, y_abs, w_abs, h_abs]

        # 4. Generate visual debugging image showing ROI overlays
        roi_debug_img = normalized_img.copy()
        for name, box in absolute_rois.items():
            x, y, w, h = box
            # Draw green rectangle
            cv2.rectangle(roi_debug_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Write key name
            cv2.putText(roi_debug_img, name, (x, max(15, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

        roi_overlay_filename = f"roi_overlay_{filename}"
        roi_overlay_path = os.path.join(self.processed_folder, roi_overlay_filename)
        cv2.imwrite(roi_overlay_path, roi_debug_img)
        logger.info(f"Saved ROI overlays debug image to: {roi_overlay_path}")

        # 5. Return mapped ROIs as requested
        return {
            "normalized_image_path": os.path.abspath(normalized_path),
            "roi_overlay_image_path": os.path.abspath(roi_overlay_path),
            "rois": absolute_rois
        }
