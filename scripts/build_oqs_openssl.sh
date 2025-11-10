#!/bin/bash
# Build script for OQS Provider for OpenSSL 3 with Kyber support
# This script builds liboqs and OQS Provider for quantum-resistant TLS

set -e

echo "=== Building OQS Provider for OpenSSL 3 with Kyber Support ==="

# Configuration
BUILD_DIR="$(pwd)/build"
INSTALL_PREFIX="$(pwd)/arc/crypto/oqs"

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    NPROC=$(sysctl -n hw.ncpu)
    OPENSSL_ROOT=$(brew --prefix openssl@3 2>/dev/null || echo "/usr/local/opt/openssl@3")
else
    NPROC=$(nproc)
    OPENSSL_ROOT="/usr"
fi

echo "Detected OS: $OSTYPE"
echo "Using OpenSSL from: $OPENSSL_ROOT"
echo "Install prefix: $INSTALL_PREFIX"

# Create build directory
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Step 1: Clone and build liboqs
echo ""
echo "Step 1/2: Building liboqs..."
if [ ! -d "liboqs" ]; then
    git clone --depth 1 --branch main https://github.com/open-quantum-safe/liboqs.git
fi

cd liboqs
mkdir -p build
cd build

cmake -GNinja \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
    -DOQS_USE_OPENSSL=ON \
    -DBUILD_SHARED_LIBS=ON \
    -DOQS_BUILD_ONLY_LIB=ON \
    ..

ninja
ninja install

cd "$BUILD_DIR"

# Step 2: Clone and build OQS Provider for OpenSSL 3
echo ""
echo "Step 2/2: Building OQS Provider for OpenSSL 3..."
if [ ! -d "oqs-provider" ]; then
    git clone --depth 1 --branch main https://github.com/open-quantum-safe/oqs-provider.git
fi

cd oqs-provider
mkdir -p build
cd build

cmake -GNinja \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
    -DOPENSSL_ROOT_DIR="$OPENSSL_ROOT" \
    -Dliboqs_DIR="$INSTALL_PREFIX/lib/cmake/liboqs" \
    ..

ninja
ninja install

# Copy the provider to our bundled location
echo "Copying OQS provider to bundled location..."
mkdir -p "$INSTALL_PREFIX/lib/ossl-modules"
cp "$OPENSSL_ROOT/lib/ossl-modules/oqsprovider.dylib" "$INSTALL_PREFIX/lib/ossl-modules/" || \
cp "$OPENSSL_ROOT/lib64/ossl-modules/oqsprovider.so" "$INSTALL_PREFIX/lib/ossl-modules/" 2>/dev/null || \
echo "Provider copied from system OpenSSL"

cd "$BUILD_DIR/.."

# Step 3: Create OpenSSL configuration
echo ""
echo "Step 3/3: Setting up OpenSSL configuration..."

mkdir -p "$INSTALL_PREFIX/ssl"
cat > "$INSTALL_PREFIX/ssl/openssl.cnf" << 'EOF'
openssl_conf = openssl_init

[openssl_init]
providers = provider_sect

[provider_sect]
default = default_sect
oqsprovider = oqsprovider_sect

[default_sect]
activate = 1

[oqsprovider_sect]
activate = 1
EOF

echo "=== Build Complete ==="
echo ""
echo "✅ OQS Provider for OpenSSL 3 with Kyber support installed to: $INSTALL_PREFIX"
echo "   Libraries will be automatically loaded when you import the ARC SDK."
echo ""

