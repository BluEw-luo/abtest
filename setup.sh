#!/usr/bin/env bash
# setup.sh — 一键安装 CLI 版依赖
set -e

cd "$(dirname "$0")"

echo "==> 创建虚拟环境（.abtest-venv）..."
uv venv .abtest-venv

echo "==> 安装依赖（sounddevice, soundfile, scipy）..."
uv pip install sounddevice soundfile scipy

echo ""
echo "  ✓ 安装完成"
echo "  用法: ./abtest.sh <音频文件1> <音频文件2>"
echo "  示例: ./abtest.sh song.flac song.mp3"
echo ""
