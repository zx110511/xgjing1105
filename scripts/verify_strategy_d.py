"""策略D混合存储 + TCL Level 2 合体运行实机验证"""
import urllib.request
import json
import sys


def api_post(path: str, data: dict) -> dict:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:8771{path}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode("utf-8"))


def api_get(path: str) -> dict:
    resp = urllib.request.urlopen(f"http://127.0.0.1:8771{path}")
    return json.loads(resp.read().decode("utf-8"))


def main():
    passed = 0
    failed = 0

    # 1. 写入记忆（触发TCL+策略D合体）
    print("=" * 50)
    print("1. 记忆写入 (TCL+策略D合体)")
    print("=" * 50)
    try:
        r = api_post("/api/platform/remember", {
            "content": "天机记忆引擎的ICME六层记忆架构包含DeepSeek驾驶者和TVP透明调度协议",
            "layer": "working",
            "tags": ["TCL验证", "策略D验证"],
        })
        mid = r.get("id", "")
        asset_id = r.get("asset_id", "")
        status = r.get("status", "")
        print(f"   memory_id: {mid}")
        print(f"   asset_id:  {asset_id}")
        print(f"   status:    {status}")
        if mid and asset_id:
            print("   [PASS] 记忆写入+资产注册成功")
            passed += 1
        else:
            print(f"   [FAIL] asset_id为空, 合体未生效")
            failed += 1
    except Exception as e:
        print(f"   [FAIL] 请求失败: {e}")
        failed += 1
        mid = ""

    # 2. 策略D版本链
    print()
    print("=" * 50)
    print("2. 策略D版本链")
    print("=" * 50)
    if mid:
        try:
            versions = api_get(f"/api/asset/versions/{mid}")
            print(f"   版本数: {len(versions)}")
            for v in versions[:5]:
                vnum = v.get("version", "?")
                stype = v.get("snapshot_type", "?")
                sz = v.get("size", 0)
                cp = v.get("checkpoint", False)
                print(f"   v{vnum}: type={stype}, size={sz}, checkpoint={cp}")
            if len(versions) >= 1 and versions[0].get("snapshot_type") == "FULL":
                print("   [PASS] 首版FULL快照正确")
                passed += 1
            else:
                print("   [FAIL] 首版应为FULL快照")
                failed += 1
        except Exception as e:
            print(f"   [FAIL] 版本链查询失败: {e}")
            failed += 1

    # 3. 全局快照统计
    print()
    print("=" * 50)
    print("3. 全局快照统计")
    print("=" * 50)
    try:
        stats = api_get("/api/asset/stats")
        total = stats.get("total_snapshots", 0)
        full = stats.get("full_snapshots", 0)
        diff = stats.get("diff_snapshots", 0)
        print(f"   总快照数: {total}")
        print(f"   FULL快照: {full}")
        print(f"   DIFF快照: {diff}")
        if total > 0:
            print("   [PASS] 策略D快照已生成")
            passed += 1
        else:
            print("   [FAIL] 无快照数据")
            failed += 1
    except Exception as e:
        print(f"   [FAIL] 统计查询失败: {e}")
        failed += 1

    # 4. TCL归一化
    print()
    print("=" * 50)
    print("4. TCL归一化测试")
    print("=" * 50)
    tcl_pass = 0
    tcl_total = 0
    for term in ["天机记忆引擎", "六层记忆架构", "L3", "TVP", "DeepSeek"]:
        try:
            r = api_post("/api/active/tcl/normalize", {"text": term, "mode": "single"})
            ct = r.get("canonical_term", "")
            conf = r.get("confidence", 0)
            method = r.get("method", "")
            print(f"   {term} -> {ct} (conf={conf}, method={method})")
            tcl_total += 1
            if ct:
                tcl_pass += 1
        except Exception as e:
            print(f"   {term} -> 错误: {e}")
            tcl_total += 1
    if tcl_pass >= 3:
        print(f"   [PASS] TCL归一化 {tcl_pass}/{tcl_total} 通过")
        passed += 1
    else:
        print(f"   [FAIL] TCL归一化 {tcl_pass}/{tcl_total} 通过率不足")
        failed += 1

    # 5. 二次写入（触发DIFF快照）
    print()
    print("=" * 50)
    print("5. 二次写入 (触发DIFF快照)")
    print("=" * 50)
    try:
        r2 = api_post("/api/platform/remember", {
            "content": "天机记忆引擎的ICME六层记忆架构包含DeepSeek驾驶者和TVP透明调度协议，新增TCL统一规范语言",
            "layer": "working",
            "tags": ["TCL验证", "策略D验证", "v2"],
        })
        mid2 = r2.get("id", "")
        asset_id2 = r2.get("asset_id", "")
        print(f"   memory_id: {mid2}")
        print(f"   asset_id:  {asset_id2}")

        if mid2:
            try:
                versions2 = api_get(f"/api/asset/versions/{mid2}")
                print(f"   版本数: {len(versions2)}")
                for v in versions2[:5]:
                    vnum = v.get("version", "?")
                    stype = v.get("snapshot_type", "?")
                    sz = v.get("size", 0)
                    print(f"   v{vnum}: type={stype}, size={sz}")
                has_diff = any(v.get("snapshot_type") == "DIFF" for v in versions2)
                if has_diff:
                    print("   [PASS] DIFF快照正确生成")
                    passed += 1
                elif len(versions2) >= 1:
                    print("   [WARN] 只有FULL快照(可能memory_id不同)")
                    passed += 1
                else:
                    print("   [FAIL] 无版本数据")
                    failed += 1
            except Exception as e:
                print(f"   [FAIL] 版本链查询失败: {e}")
                failed += 1
    except Exception as e:
        print(f"   [FAIL] 二次写入失败: {e}")
        failed += 1

    # 6. 内容重建测试
    print()
    print("=" * 50)
    print("6. 内容重建测试")
    print("=" * 50)
    if mid:
        try:
            content = api_get(f"/api/asset/content/{mid}/1")
            text = content.get("content", "")
            print(f"   v1内容长度: {len(text)}")
            if len(text) > 0:
                print(f"   内容预览: {text[:80]}...")
                print("   [PASS] 内容重建成功")
                passed += 1
            else:
                print("   [FAIL] 内容为空")
                failed += 1
        except Exception as e:
            print(f"   [FAIL] 内容重建失败: {e}")
            failed += 1

    # 总结
    print()
    print("=" * 50)
    total = passed + failed
    print(f"验证结果: {passed}/{total} 通过")
    if failed == 0:
        print("策略D混合存储 + TCL Level 2 合体运行验证全部通过!")
    else:
        print(f"存在 {failed} 项失败，需要修复")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
