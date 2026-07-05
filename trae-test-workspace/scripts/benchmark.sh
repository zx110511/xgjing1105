#!/usr/bin/env bash
# Trae测试工作区基准测试脚本

set -e

echo ""=============================================""
echo ""  运行性能基准测试""
echo ""=============================================""
echo """"

# Python基准测试
echo ""[1/2] Python基准测试...""
cd python
source venv/bin/activate || . venv/Scripts/activate
pytest tests/ --benchmark-only --benchmark-autosave --benchmark-compare=previous
cd ..

# TypeScript基准测试
echo ""[2/2] TypeScript基准测试...""
if [ -f ""typescript/package.json"" ]; then
    cd typescript
    npm run benchmark || true
    cd ..
fi

echo """"
echo ""=============================================""
echo ""  基准测试完成！""
echo ""=============================================""
