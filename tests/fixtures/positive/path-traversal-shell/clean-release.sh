#!/usr/bin/env bash
# clean-release: xóa output build cũ trước khi đóng gói

echo "cleaning ${BUILD_DIR}"
rm -rf "$BUILD_DIR/"*
