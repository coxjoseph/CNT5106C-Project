#!/usr/bin/env python3
import argparse
import asyncio
import os
from pathlib import Path
import logging
from util.logging_config import configure_logging

from net.connector import Connector
from logic.peer_node import PeerNode
from util.config import CommonConfig, PeerInfoTable, PeerRow
import contextlib


async def main() -> None:
    peer_id = get_peer_id()
    configure_logging(peer_id, to_console=True, log_dir=".")

    common, peers, me = load_configs(peer_id)
    work_dir, data_dir, start_full = await prepare_directories(peer_id, common, me)
    node = build_node(common, peers, data_dir, start_full, peer_id)
    connector = build_connector(me, peer_id, node)
    await run_network(node, connector, peers)


def get_peer_id() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("peer_id", type=int)
    args = ap.parse_args()
    return args.peer_id


def load_configs(peer_id: int) -> tuple[CommonConfig, PeerInfoTable, PeerRow]:
    common = CommonConfig.from_file("Common.cfg")
    peers = PeerInfoTable.from_file("PeerInfo.cfg")
    me = peers.get(peer_id)
    return common, peers, me


async def prepare_directories(peer_id: int, common, me) -> tuple[Path, Path, bool]:
    work_dir = Path.cwd() / f"peer_{peer_id}"
    data_dir = work_dir / "pieces"
    data_dir.mkdir(parents=True, exist_ok=True)

    start_full = me.has_file == 1
    if start_full:
        await ensure_seed_has_pieces(work_dir, common, peer_id)
    return work_dir, data_dir, start_full


async def ensure_seed_has_pieces(work_dir: Path, common, peer_id: int) -> None:
    src = work_dir / common.file_name
    if not src.exists():
        raise FileNotFoundError(f"Seed peer {peer_id} missing source file: {src}")

    pieces = list((work_dir / "pieces").glob("piece_*.bin"))
    if len(pieces) != common.total_pieces:
        await slice_into_pieces(
            src,
            work_dir / "pieces",
            common.piece_size,
            common.total_pieces,
            common.last_piece_size,
        )


def build_node(common, peers, data_dir, start_full, peer_id: int) -> PeerNode:
    return PeerNode(
        total_pieces=common.total_pieces,
        piece_size=common.piece_size,
        last_piece_size=common.last_piece_size,
        data_dir=str(data_dir),
        start_with_full_file=start_full,
        k_preferred=common.num_preferred_neighbors,
        preferred_interval_sec=common.unchoking_interval,
        optimistic_interval_sec=common.optimistic_unchoking_interval,
        self_id=peer_id,
        all_peer_ids={r.peer_id for r in peers.rows},
        file_name=common.file_name,
    )


def build_connector(me, peer_id: int, node: PeerNode) -> Connector:
    connector = Connector(
        me.host,
        me.port,
        local_peer_id=peer_id,
        logic_factory=node.make_callbacks,
    )
    node.connector = connector
    return connector


async def run_network(node: PeerNode, connector: Connector, peers) -> None:
    _ = asyncio.create_task(connector.serve())
    for row in peers.earlier_peers(node.self_id):
        _ = asyncio.create_task(connector.connect_with_retry(row.host, row.port))

    choke_task = asyncio.create_task(node.run_choking_loops())
    try:
        await node.wait_until_all_complete()
    finally:
        choke_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await choke_task
        node.store.reconstruct_full_file(node.file_name)
        node.store.cleanup_pieces()
        await connector.close_all()


async def slice_into_pieces(src_path: Path, out_dir: Path, piece_size: int, total_pieces: int,
                            last_piece_size: int) -> None:
    data = src_path.read_bytes()
    offset = 0
    for i in range(total_pieces):
        size = last_piece_size if i == total_pieces - 1 else piece_size
        chunk = data[offset: offset + size]
        if len(chunk) != size:
            raise ValueError(f'Source file too small for piece {i} (expected {size}, got {len(chunk)})')
        (out_dir / f'piece_{i:06d}.bin').write_bytes(chunk)
        offset += size


if __name__ == '__main__':
    asyncio.run(main())
