"""强制清理Meta层 - 绕过API直接操作"""
import sys
import json

# 添加路径
sys.path.insert(0, r"D:\元初系统\天机v9.1")

def cleanup_meta():
    """通过API清理Meta层"""
    import urllib.request

    url = "http://127.0.0.1:8771/api/memory/storage/manage"
    cleaned_total = 0
    round_num = 0

    while round_num < 50:
        round_num += 1
        data = json.dumps({
            "layer": "meta",
            "action": "emergency_consolidate",
            "force": True,
            "max_entries": 500
        }).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

                for action in result.get("actions_performed", []):
                    if action.get("action") == "force_evict":
                        before = action.get("before", 0)
                        after = action.get("after", 0)
                        evicted = action.get("evicted", 0)
                        cleaned_total += evicted
                        print(f"Round {round_num}: {before} → {after} (evicted: {evicted})")

                        if after <= 1000 or evicted == 0:
                            print(f"\n✅ Cleanup complete! Total removed: {cleaned_total}")
                            return True
        except Exception as e:
            print(f"Round {round_num}: Error - {e}")
            break

    print(f"\nCleanup stopped. Total removed: {cleaned_total}")
    return False

if __name__ == "__main__":
    cleanup_meta()
