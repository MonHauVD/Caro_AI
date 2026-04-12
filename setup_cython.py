from setuptools import Extension, setup

try:
    from Cython.Build import cythonize
except ImportError as exc:
    raise SystemExit(
        "Cython is not installed. Run: pip install cython"
    ) from exc


extensions = [
    Extension(
        "agent_accel",
        ["extensions/agent_accel.pyx"],
    ),
    Extension(
        "search_accel",
        ["extensions/search_accel.pyx"],
    ),
]

setup(
    name="caro-ai-cython",
    ext_modules=cythonize(
        extensions,
        compiler_directives={"language_level": "3"},
    ),
)
