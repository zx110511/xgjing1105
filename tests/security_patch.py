"""安全补丁: 为_conv_file添加UUID校验防止路径遍历"""
import pathlib

p = pathlib.Path(r"D:\元初系统\天机v9.1\server\api\chat_routes.py")
content = p.read_text(encoding="utf-8")

old = 'def _conv_file(conv_id: str) -> str:\n    return os.path.join(_CONVERSATIONS_DIR, f"{conv_id}.json")'

new = '''def _conv_file(conv_id: str) -> str:
    # 安全校验: conv_id必须是合法UUID格式, 防止路径遍历
    try:
        uuid.UUID(conv_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID format")
    return os.path.join(_CONVERSATIONS_DIR, f"{conv_id}.json")'''

if old in content:
    content = content.replace(old, new, 1)
    p.write_text(content, encoding="utf-8")
    print("PATCHED: _conv_file UUID validation added")
else:
    print("SKIP: pattern not found (may already be patched)")
