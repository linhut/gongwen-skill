# gongwen-skill 开发工作流
# ============================================================
# (c) 2026 Jose AI (https://www.linhut.cn)  MIT License
#
# 常用命令：
#   make install    — 安装依赖
#   make test       — 运行全部测试
#   make check      — 快速验证（test 别名）
#   make list-types — 列出支持的公文类型
#   make clean      — 清理缓存和临时文件

.PHONY: install test check list-types clean version help

help:
	@echo "gongwen-skill 开发工作流"
	@echo "========================"
	@echo "make install     安装依赖 (pip install -r requirements.txt)"
	@echo "make test        运行全部测试"
	@echo "make check       test 的别名"
	@echo "make list-types  列出 22 种公文类型"
	@echo "make version     显示版本"
	@echo "make clean       清理 __pycache__ / .pytest_cache / 临时文件"
	@echo ""

install:
	pip install -r requirements.txt

test:
	python -m pytest tests/ -v --tb=short

check: test

list-types:
	python gongwen.py list-types

version:
	python gongwen.py --version

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache/ 2>/dev/null || true
	@echo "清理完成"
