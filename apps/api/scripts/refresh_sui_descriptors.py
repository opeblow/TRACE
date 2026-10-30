"""Refresh the vendored Sui gRPC schema from the Tatum gateway.

Usage (from apps/api, with TATUM_MAINNET_API_KEY in the environment or .env):
    python scripts/refresh_sui_descriptors.py

Requires grpcio-reflection (dev only). Writes app/services/sui_rpc_v2.binpb, a
FileDescriptorSet for sui.rpc.v2 LedgerService and StateService. Re-run when
Tatum upgrades its Sui node and commit the result after the tests pass.
"""
import os
import sys
from pathlib import Path

import grpc
from dotenv import load_dotenv
from google.protobuf import descriptor_pb2
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc

API_DIR = Path(__file__).resolve().parents[1]
OUTPUT = API_DIR / "app" / "services" / "sui_rpc_v2.binpb"
TARGET = os.environ.get("TATUM_GRPC_TARGET", "sui-mainnet-grpc.gateway.tatum.io:443")
SERVICES = ["sui.rpc.v2.LedgerService", "sui.rpc.v2.StateService"]


def main() -> int:
    load_dotenv(API_DIR / ".env")
    key = os.environ.get("TATUM_MAINNET_API_KEY", "").strip()
    if not key:
        print("TATUM_MAINNET_API_KEY is not set", file=sys.stderr)
        return 1
    metadata = [("x-api-key", key)]
    channel = grpc.secure_channel(TARGET, grpc.ssl_channel_credentials())
    stub = reflection_pb2_grpc.ServerReflectionStub(channel)
    files: dict[str, descriptor_pb2.FileDescriptorProto] = {}

    def fetch(request):
        for response in stub.ServerReflectionInfo(iter([request]), metadata=metadata, timeout=20):
            for raw in response.file_descriptor_response.file_descriptor_proto:
                proto = descriptor_pb2.FileDescriptorProto.FromString(raw)
                files[proto.name] = proto
            return

    for service in SERVICES:
        fetch(reflection_pb2.ServerReflectionRequest(file_containing_symbol=service))
    pending = True
    while pending:
        pending = False
        for proto in list(files.values()):
            for dependency in proto.dependency:
                if dependency not in files:
                    fetch(reflection_pb2.ServerReflectionRequest(file_by_filename=dependency))
                    pending = True

    ordered: list[descriptor_pb2.FileDescriptorProto] = []
    seen: set[str] = set()

    def visit(name: str):
        if name in seen:
            return
        seen.add(name)
        for dependency in files[name].dependency:
            visit(dependency)
        ordered.append(files[name])

    for name in sorted(files):
        visit(name)
    OUTPUT.write_bytes(descriptor_pb2.FileDescriptorSet(file=ordered).SerializeToString())
    print(f"Wrote {len(ordered)} files to {OUTPUT.relative_to(API_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
