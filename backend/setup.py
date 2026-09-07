from setuptools import setup, find_packages

# Cython build is optional — pure Python fallback always available
try:
    from Cython.Build import cythonize
    import numpy as np

    ext_modules = cythonize(
        [
            "engine/event_queue_cy.pyx",
            "engine/order_book_cy.pyx",
            "engine/matching_engine_cy.pyx",
            "engine/latency_model_cy.pyx",
        ],
        language_level=3,
    )
    include_dirs = [np.get_include()]
except ImportError:
    ext_modules = []
    include_dirs = []
    print(
        "WARNING: Cython not found — building pure Python only. "
        "Install Cython and NumPy for accelerated mode."
    )

setup(
    name="hft-backtester",
    version="0.1.0",
    packages=find_packages(),
    ext_modules=ext_modules,
    include_dirs=include_dirs,
    python_requires=">=3.11",
)
