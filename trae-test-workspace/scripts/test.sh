#!/usr/bin/env bash
# Trae测试工作区测试脚本

set -e

echo ""=============================================""
echo ""  运行所有测试""
echo ""=============================================""
echo """"

# Python测试
echo ""[1/3] Python测试...""
cd python
source venv/bin/activate || . venv/Scripts/activate
pytest tests/ -v --cov=src --cov-report=html:../reports/coverage/python
cd ..

# TypeScript测试
echo ""[2/3] TypeScript测试...""
if [ -f ""typescript/package.json"" ]; then
    cd typescript
    npm test || true
    cd ..
fi

# 集成测试
echo ""[3/3] 集成测试...""
pytest integration/ -v -m integration || true

echo """"
echo ""=============================================""
echo ""  测试完成！""
echo ""=============================================""
