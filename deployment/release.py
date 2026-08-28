"""Promote or roll back Azure ML online endpoint traffic safely."""

from __future__ import annotations

import argparse

from src.azure_config import WorkspaceConfig


def build_traffic_split(
    *,
    candidate: str,
    candidate_percentage: int,
    stable: str | None,
) -> dict[str, int]:
    """Return a complete 100-percent traffic allocation."""
    if not 0 <= candidate_percentage <= 100:
        raise ValueError("candidate_percentage must be between 0 and 100")
    if candidate_percentage < 100 and not stable:
        raise ValueError("A stable deployment is required below 100% candidate traffic")
    if stable == candidate:
        raise ValueError("Stable and candidate deployments must be different")
    traffic = {candidate: candidate_percentage}
    if stable:
        traffic[stable] = 100 - candidate_percentage
    return {name: value for name, value in traffic.items() if value > 0}


def parse_args() -> argparse.Namespace:
    """Parse release traffic arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--stable")
    parser.add_argument("--candidate-percentage", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    """Apply an explicit canary, promotion, or rollback traffic split."""
    args = parse_args()
    client = WorkspaceConfig.from_environment().create_client()
    endpoint = client.online_endpoints.get(args.endpoint)
    endpoint.traffic = build_traffic_split(
        candidate=args.candidate,
        candidate_percentage=args.candidate_percentage,
        stable=args.stable,
    )
    client.online_endpoints.begin_create_or_update(endpoint).result()
    print(f"Traffic updated: {endpoint.traffic}")


if __name__ == "__main__":
    main()
