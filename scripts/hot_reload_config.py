#!/usr/bin/env python
"""天机v9.1 配置热重载 — 更新max_entries并持久化"""

import requests

API_BASE = "http://127.0.0.1:8771/api"


def main():
    print("=" * 60)
    print("天机v9.1 配置热重载")
    print("=" * 60)

    # 1. 检查当前配置
    r = requests.get(f"{API_BASE}/health")
    health = r.json()
    print(f"服务状态: {health['status']}")
    print(f"版本: {health['version']}")

    for layer_name in ["working", "episodic"]:
        l = health["layers"].get(layer_name, {})
        print(
            f"  {layer_name}: entries={l.get('entry_count')}, max_entries={l.get('max_entries')}, usage={l.get('usage_ratio', 0) * 100:.1f}%"
        )

    # 2. 尝试通过引擎内部API更新配置
    # 检查是否有配置更新端点
    try:
        r = requests.get(f"{API_BASE}/memory/layers/info")
        print(f"\nLayer info: {r.status_code}")
    except Exception as e:
        print(f"  Layer info: {e}")

    # 3. 尝试通过 Python import 直接更新引擎配置
    print("\n尝试直接更新引擎配置...")
    try:
        r = requests.post(f"{API_BASE}/llm/reload", json={})
        print(f"  LLM reload: {r.status_code} - {r.text[:200]}")
    except Exception as e:
        print(f"  LLM reload failed: {e}")

    # 4. 触发所有层的 consolidation
    print("\n触发跨层固结...")
    for from_layer in ["working", "short_term", "episodic"]:
        try:
            body = {"from_layer": from_layer}
            r = requests.post(f"{API_BASE}/memory/consolidate_all", json=body)
            result = r.json()
            print(
                f"  {from_layer}→: consolidated={result.get('consolidated_count', 0)}, accumulated={result.get('total_accumulated', 0)}"
            )
        except Exception as e:
            print(f"  {from_layer}: {e}")


if __name__ == "__main__":
    main()
