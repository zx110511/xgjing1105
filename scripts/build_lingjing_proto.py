"""
Tianji v8.2 Lingjing Proto Builder
=====================================
Compiles lingjing.proto into Python stubs.

Usage: python scripts/build_lingjing_proto.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROTO_DIR = PROJECT_ROOT / "proto"
PROTO_FILE = PROTO_DIR / "lingjing.proto"
GEN_DIR = PROJECT_ROOT / "proto"

PASS = "[PASS]"
FAIL = "[FAIL]"

def main():
    print("Building Lingjing gRPC Protocol...")
    print(f"  Proto: {PROTO_FILE}")
    print(f"  Exists: {PROTO_FILE.exists()}")

    if not PROTO_FILE.exists():
        print(f"  {FAIL} lingjing.proto not found")
        return False

    try:
        from grpc_tools import protoc
        import grpc_tools
        print(f"  {PASS} grpcio-tools available: {grpc_tools.__version__ if hasattr(grpc_tools, '__version__') else 'ok'}")

        sys.path.insert(0, str(PROJECT_ROOT))
        args = [
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={GEN_DIR}",
            f"--grpc_python_out={GEN_DIR}",
            str(PROTO_FILE),
        ]

        result = protoc.main(args)
        if result == 0:
            stub = GEN_DIR / "lingjing_pb2.py"
            grpc_stub = GEN_DIR / "lingjing_pb2_grpc.py"
            print(f"  {PASS} proto compiled: pb2={stub.exists()}, grpc={grpc_stub.exists()}")

            init_file = GEN_DIR / "__init__.py"
            if not init_file.exists():
                init_file.touch()

            return True
        else:
            print(f"  {FAIL} protoc returned {result}")
            return False

    except ImportError as e:
        print(f"  {WARN} Cannot build proto: {e}")
        print(f"  Install: pip install grpcio-tools")
        return False
    except Exception as e:
        print(f"  {FAIL} {e}")
        return False


WARN = "[WARN]"

if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
