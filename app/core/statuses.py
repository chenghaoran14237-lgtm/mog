class RecordStatus:
    UPLOADED = "uploaded"
    OCR_PROCESSING = "ocr_processing"
    OCR_COMPLETED = "ocr_completed"
    OCR_FAILED = "ocr_failed"
    NORMALIZATION_PROCESSING = "normalization_processing"
    NORMALIZED = "normalized"
    NORMALIZATION_FAILED = "normalization_failed"


class OCRStatus:
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class NormalizationStatus:
    PROCESSING = "processing"
    NORMALIZED = "normalized"
    FAILED = "failed"


class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType:
    OCR = "ocr"
    NORMALIZATION = "normalization"
