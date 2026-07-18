#!/usr/bin/env bash
# generate-test.sh — 生成两首不同采样率的测试音频（WAV + FLAC）
set -e

cd "$(dirname "$0")"

echo "==> 生成测试音频（5 秒）..."

python3 -c "
import numpy as np
import soundfile as sf

sr1, sr2 = 44100, 96000
dur = 5
t1 = np.linspace(0, dur, int(sr1*dur), False)
t2 = np.linspace(0, dur, int(sr2*dur), False)

# File 1: 440Hz+880Hz sine, 44.1kHz WAV
wav1 = 0.5 * (np.sin(2*np.pi*440*t1) + np.sin(2*np.pi*880*t1))
sf.write('test_44k.wav', wav1, sr1)
print(f'  ✓ test_44k.wav  ({sr1} Hz)')

# File 2: same + subtle 3rd/4th harmonic, 96kHz FLAC
wav2 = 0.5 * (np.sin(2*np.pi*440*t2) + np.sin(2*np.pi*880*t2)
              + 0.05*np.sin(2*np.pi*1320*t2)
              + 0.03*np.sin(2*np.pi*1760*t2))
sf.write('test_96k.flac', wav2, sr2)
print(f'  ✓ test_96k.flac ({sr2} Hz)')
"

echo "  测试文件已生成，可用于验证工具是否正常工作。"
echo "  浏览器: 打开 index.html，选择这两首文件"
echo "  CLI:    ./abtest.sh test_44k.wav test_96k.flac"
echo ""
