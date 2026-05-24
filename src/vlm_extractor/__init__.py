# """VLM-based site sketch extraction for the Soil Co-Lab pipeline.

# Usage
# -----

#     from vlm_extractor import extract_from_image, to_cell_data

#     result = extract_from_image("sketch.jpg", backend="gemini")
#     if result.ok:
#         cell_data = to_cell_data(result.data, yard_choice="Back")
#         # cell_data now drops straight into site_builder.py's
#         # existing Compute path — same shape as if a human had
#         # typed every field.
#     else:
#         for p in result.problems:
#             print("⚠️", p)
# """

# from .providers import ExtractionResult, extract_from_image
# from .schema import (
#     SITE_SKETCH_SCHEMA,
#     normalize_extraction,
#     to_cell_data,
#     validate_extraction,
# )

# __all__ = [
#     "ExtractionResult",
#     "SITE_SKETCH_SCHEMA",
#     "extract_from_image",
#     "normalize_extraction",
#     "to_cell_data",
#     "validate_extraction",
# ]

"""VLM-based site sketch extraction for the Soil Co-Lab pipeline.

Usage
-----

    from vlm_extractor import extract_from_image, to_cell_data

    result = extract_from_image("sketch.jpg", backend="gemini")
    if result.ok:
        cell_data = to_cell_data(result.data, yard_choice="Back")
        # cell_data now drops straight into site_builder.py's
        # existing Compute path — same shape as if a human had
        # typed every field.
    else:
        for p in result.problems:
            print("⚠️", p)
"""

from .providers import ExtractionResult, extract_from_image
from .schema import (
    SITE_SKETCH_SCHEMA,
    normalize_extraction,
    to_cell_data,
    validate_extraction,
)

# The Streamlit UI is imported lazily so this package can be used from
# non-Streamlit contexts (test scripts, headless extraction, CI).
# Calling `from vlm_extractor import render_vlm_section` will trigger
# the import; otherwise Streamlit is never required.
def __getattr__(name):
    if name == "render_vlm_section":
        from .streamlit_ui import render_vlm_section
        return render_vlm_section
    raise AttributeError(f"module 'vlm_extractor' has no attribute {name!r}")


__all__ = [
    "ExtractionResult",
    "SITE_SKETCH_SCHEMA",
    "extract_from_image",
    "normalize_extraction",
    "render_vlm_section",
    "to_cell_data",
    "validate_extraction",
]