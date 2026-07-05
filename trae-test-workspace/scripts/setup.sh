#!/usr/bin/env bash
# Trae测试工作区初始化脚本

set -e

echo ""=============================================""
echo ""  Trae测试工作区初始化""
echo ""=============================================""
echo """"

# 初始化Python环境
echo ""[1/3] 初始化Python环境...""
cd python
if [ ! -d ""venv"" ]; then
    python3 -m venv venv
fi
source venv/bin/activate || . venv/Scripts/activate
pip install -r requirements.txt
cd ..

# 初始化Node.js环境
echo ""[2/3] 初始化Node.js环境...""
if [ -f ""typescript/package.json"" ]; then
    cd typescript
    npm install || true
    cd ..
fi

# 创建测试报告目录
echo ""[3/3] 创建测试报告目录...""
mkdir -p reports/coverage
mkdir -p reports/benchmark
mkdir -p reports/integration

echo """"
echo ""=============================================""
echo ""  初始化完成！""
echo ""=============================================""
echo """"
echo ""运行测试:""
echo ""  ./scripts/test.sh""
echo """"
echo ""运行基准测试:""
echo ""  ./scripts/benchmark.sh""
