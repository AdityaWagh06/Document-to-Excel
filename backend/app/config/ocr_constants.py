# OCR Preprocessing and Service Settings

TARGET_WIDTH = 1600

# Bilateral filter parameters
BILATERAL_D = 9
BILATERAL_SIGMA_COLOR = 75
BILATERAL_SIGMA_SPACE = 75

# Adaptive threshold parameters
THRESHOLD_MAX_VALUE = 255
THRESHOLD_BLOCK_SIZE = 41
THRESHOLD_C = 10

# Sharpening kernel matrix
SHARPEN_KERNEL = [[0, -1, 0], [-1, 5, -1], [0, -1, 0]]

# EasyOCR parameters
EASYOCR_LANGUAGES = ["en"]

# PaddleOCR parameters
PADDLEOCR_LANG = "en"

# OCR Pipeline Fallback threshold
OCR_CONFIDENCE_THRESHOLD = 0.75

# PDF Rendering Parameters
DEFAULT_PDF_RENDER_DPI = 150
DEFAULT_MAX_PDF_PAGES = 20
MAX_RENDER_PIXELS_PER_PAGE = 25_000_000
