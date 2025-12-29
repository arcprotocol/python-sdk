#!/usr/bin/env python3
"""
ARC Python SDK Setup
"""

from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop
import subprocess
import sys
import os

# Read README for long description
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]


def check_build_dependencies():
    """
    Check if required build dependencies are installed.
    Fails installation with clear error message if dependencies are missing.
    """
    missing_deps = []
    install_instructions = []
    
    # Check for cmake
    try:
        subprocess.run(["cmake", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing_deps.append("CMake")
        if sys.platform == "darwin":
            install_instructions.append("  brew install cmake")
        else:
            install_instructions.append("  sudo apt-get install cmake  # Debian/Ubuntu")
            install_instructions.append("  sudo yum install cmake      # RedHat/CentOS")
    
    # Check for ninja
    try:
        subprocess.run(["ninja", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        missing_deps.append("Ninja")
        if sys.platform == "darwin":
            install_instructions.append("  brew install ninja")
        else:
            install_instructions.append("  sudo apt-get install ninja-build  # Debian/Ubuntu")
            install_instructions.append("  sudo yum install ninja-build      # RedHat/CentOS")
    
    # Check for C compiler
    compiler_found = False
    for compiler in ["cc", "gcc", "clang"]:
        try:
            subprocess.run([compiler, "--version"], capture_output=True, check=True)
            compiler_found = True
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    if not compiler_found:
        missing_deps.append("C Compiler (gcc/clang)")
        if sys.platform == "darwin":
            install_instructions.append("  xcode-select --install")
        else:
            install_instructions.append("  sudo apt-get install build-essential  # Debian/Ubuntu")
            install_instructions.append("  sudo yum groupinstall 'Development Tools'  # RedHat/CentOS")
    
    if missing_deps:
        print("\n" + "="*70)
        print("❌ ERROR: Missing required dependencies for PQC support")
        print("="*70)
        print(f"\nMissing dependencies: {', '.join(missing_deps)}")
        print("\nTo install the missing dependencies, run:\n")
        for instruction in install_instructions:
            print(instruction)
        print("\nThen try installing again:")
        print("  pip install arc-sdk[pqc]")
        print("\n" + "="*70 + "\n")
        sys.exit(1)


def build_oqs_libraries():
    """
    Build OQS libraries (liboqs + OQS Provider) during installation.
    Enables post-quantum cryptography support for the SDK.
    """
    print("\n" + "="*70)
    print("Building OQS Provider for post-quantum cryptography...")
    print("This may take a few minutes on first install.")
    print("="*70 + "\n")
    
    # Check dependencies first
    check_build_dependencies()
    
    build_script = os.path.join(os.path.dirname(__file__), "scripts", "build_oqs_openssl.sh")
    
    if not os.path.exists(build_script):
        print("\n❌ ERROR: Build script not found.")
        print("Cannot build PQC libraries.")
        sys.exit(1)
    
    try:
        # Make script executable
        os.chmod(build_script, 0o755)
        
        # Run build script
        result = subprocess.run(
            ["bash", build_script],
            cwd=os.path.dirname(__file__),
            check=True,
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        print("\n✅ PQC libraries built successfully!\n")
        
    except subprocess.CalledProcessError as e:
        print("\n" + "="*70)
        print("❌ ERROR: Failed to build PQC libraries")
        print("="*70)
        print("\nBuild output:")
        print(e.stderr)
        print("\nPlease report this issue at:")
        print("  https://github.com/arcprotocol/python-sdk/issues")
        print("\n" + "="*70 + "\n")
        sys.exit(1)
    except Exception as e:
        print("\n" + "="*70)
        print("❌ ERROR: Unexpected error building PQC libraries")
        print("="*70)
        print(f"\nError: {e}")
        print("\nPlease report this issue at:")
        print("  https://github.com/arcprotocol/python-sdk/issues")
        print("\n" + "="*70 + "\n")
        sys.exit(1)


class CustomInstallCommand(install):
    """Custom install command that builds OQS libraries if pqc extra is requested."""
    def run(self):
        # Check if user requested pqc extra
        if any('pqc' in arg for arg in sys.argv):
            build_oqs_libraries()
        install.run(self)


class CustomDevelopCommand(develop):
    """Custom develop command that builds OQS libraries if pqc extra is requested."""
    def run(self):
        # Only build if pqc extra is requested
        if any('pqc' in arg for arg in sys.argv):
            build_oqs_libraries()
        develop.run(self)

setup(
    name="arc-sdk",
    version="1.3.1",
    author="Moein Roghani",
    author_email="moein.roghani@proton.me",
    description="Python implementation of the Agent Remote Communication (ARC) Protocol",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/arcprotocol/python-sdk",
    project_urls={
        "Bug Tracker": "https://github.com/arcprotocol/python-sdk/issues",
        "Documentation": "https://docs.arc-protocol.org",
        "Protocol Specification": "https://arc-protocol.org/spec",
        "Source Code": "https://github.com/arcprotocol/python-sdk",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Environment :: Web Environment",
        "Environment :: Console",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Communications",
        "Topic :: System :: Distributed Computing",
        "Topic :: System :: Networking",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Typing :: Typed",
    ],
    packages=find_packages(exclude=["tests*", "examples*"]),
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "server": ["fastapi>=0.104.0", "uvicorn[standard]>=0.24.0"],
        "client": ["httpx>=0.25.0"],
        "fastapi": ["fastapi>=0.104.0"],
        "starlette": ["starlette>=0.27.0"],
        "validation": ["pydantic>=2.0.0", "jsonschema>=4.19.0"],
        "pqc": [],  # Post-Quantum Cryptography: builds liboqs + OQS Provider during install
        "all": ["fastapi>=0.104.0", "starlette>=0.27.0", "uvicorn[standard]>=0.24.0", "httpx>=0.25.0", "pydantic>=2.0.0", "jsonschema>=4.19.0"],
        "dev": ["pytest>=7.0.0", "pytest-asyncio>=0.21.0", "black>=23.0.0", "flake8>=6.0.0", "mypy>=1.5.0"],
    },
    entry_points={
        "console_scripts": [
            "arc=arc.cli:main",
            "arc-validate=arc.utils.validation:validate_cli",
            "arc-schema=arc.utils.schema:main",
            "arc-agent-card=arc.utils.agent_card:main",
        ],
    },
    include_package_data=True,
    package_data={
        "arc": [
            "*.yaml", 
            "*.yml", 
            "schemas/*.json",
            "examples/*.json", 
            "templates/*.py",
            "crypto/oqs/lib/*.so*",
            "crypto/oqs/lib/*.dylib*",
            "crypto/oqs/lib/*.dll",
            "crypto/oqs/ssl/*",
        ],
    },
    cmdclass={
        'install': CustomInstallCommand,
        'develop': CustomDevelopCommand,
    },
    zip_safe=False,
)
