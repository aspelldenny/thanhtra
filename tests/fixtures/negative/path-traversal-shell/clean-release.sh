#!/usr/bin/env bash
# clean-release: xóa output build cũ (đã guard biến rỗng/unset)
set -euo pipefail

echo "cleaning ${BUILD_DIR:?BUILD_DIR not set}"
rm -rf -- "${BUILD_DIR:?}/"*
