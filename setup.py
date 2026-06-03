"""Setup script for TML platform."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    requirements = requirements_path.read_text().strip().split('\n')
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith('#')]

setup(
    name="tml-platform",
    version="0.1.0",
    description="Transaction-based Machine Learning Platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="TML Team",
    author_email="team@tml-platform.com",
    url="https://github.com/tml-platform/tml",
    packages=find_packages(exclude=["tests*", "docs*", "examples*"]),
    include_package_data=True,
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "pytest-cov>=4.1.0",
            "black>=23.11.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
        ],
        "vowpal": [
            "vowpalwabbit>=9.8.0",
        ],
        "monitoring": [
            "prometheus-client>=0.19.0",
            "grafana-api>=1.0.3",
        ],
        "deployment": [
            "kubernetes>=28.1.0",
            "docker>=6.1.3",
        ],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="machine-learning online-learning streaming incremental-learning",
    entry_points={
        "console_scripts": [
            "tml=scripts.start_platform:cli",
            "tml-server=tml.serving.api_server:run_server",
            "tml-processor=tml.ingestion.kafka_consumer:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/tml-platform/tml/issues",
        "Source": "https://github.com/tml-platform/tml",
        "Documentation": "https://tml-platform.readthedocs.io/",
    },
)
