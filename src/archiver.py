#!/usr/bin/env python3
"""
小型文件归档器 - 华为云 OBS 版本

将大量小文件打包成 tar 存储到 OBS，清单保存为 JSON 文件。

Usage:
    python archiver.py --src-path /data/files --bucket my-bucket --prefix archive/20260821
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import List, Dict, Any, Optional

try:
    from obs import ObsClient, exception
except ImportError:
    print("Error: 请安装华为云 OBS SDK: pip install esdk-obs_python")
    sys.exit(1)


class ObsArchiveConfig:
    """OBS 归档配置"""

    def __init__(self, bucket: str, prefix: str, endpoint: str,
                 access_key: str, secret_key: str,
                 workers: int = None, tar_size_mb: int = 20,
                 scan_threads: int = 8, compute_md5: bool = True):
        self.bucket = bucket
        self.prefix = prefix.rstrip('/')
        self.endpoint = endpoint or os.environ.get('HW_OBS_ENDPOINT', 'obs.cn-north-4.myhuaweicloud.com')
        self.access_key = os.environ.get('HUAWEICLOUD_ACCESS_KEY') if not access_key else access_key
        self.secret_key = os.environ.get('HUAWEICLOUD_SECRET_KEY') if not secret_key else secret_key
        self.workers = workers or os.cpu_count()
        self.tar_size_mb = tar_size_mb
        self.scan_threads = scan_threads
        self.compute_md5 = compute_md5

        if not self.access_key or not self.secret_key:
            raise ValueError("请设置 HUAWEICLOUD_ACCESS_KEY 和 HUAWEICLOUD_SECRET_KEY 环境变量或命令行参数")

    def get_obs_client(self) -> ObsClient:
        """创建 OBS 客户端"""
        return ObsClient(
            access_key_id=self.access_key,
            secret_access_key=self.secret_key,
            server=self.endpoint
        )


class FileEntry:
    """文件条目"""

    def __init__(self, rel_path: str, abs_path: str, size: int, md5: str = None):
        self.rel_path = rel_path
        self.abs_path = abs_path
        self.size = size
        self.md5 = md5


class TarBatch:
    """tar 批次"""

    def __init__(self, batch_id: int):
        self.batch_id = batch_id
        self.files: List[FileEntry] = []
        self.total_size = 0

    def add(self, file_entry: FileEntry, max_size: int) -> bool:
        """添加文件，如果超量则返回 False"""
        if self.total_size + file_entry.size > max_size:
            return False
        self.files.append(file_entry)
        self.total_size += file_entry.size
        return True


def scan_files(src_path: str, scan_threads: int = 8) -> Queue:
    """多线程扫描文件"""
    file_queue = Queue()
    src_path = Path(src_path).resolve()

    def scan_worker(path: Path):
        try:
            for item in path.rglob('*'):
                if item.is_file():
                    rel_path = item.relative_to(src_path).as_posix()
                    file_queue.put((str(item), rel_path, item.stat().st_size))
        except Exception as e:
            print(f"扫描错误: {e}")

    # 启动扫描线程
    threads = []
    for _ in range(scan_threads):
        t = threading.Thread(target=scan_worker, args=(src_path,))
        t.start()
        threads.append(t)

    # 等待扫描完成
    for t in threads:
        t.join()

    return file_queue


def compute_md5(file_path: str, chunk_size: int = 8192) -> str:
    """计算文件 MD5"""
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def create_tar(batch: TarBatch, temp_dir: str) -> str:
    """创建 tar 文件"""
    import tarfile

    tar_filename = os.path.join(temp_dir, f"archive_{batch.batch_id:05d}.tar")
    with tarfile.open(tar_filename, 'w') as tar:
        for file_entry in batch.files:
            tar.add(file_entry.abs_path, arcname=file_entry.rel_path)

    return tar_filename


def upload_to_obs(obs_client: ObsClient, bucket: str, key: str, file_path: str) -> bool:
    """上传文件到 OBS"""
    try:
        resp = obs_client.putFile(bucket, key, file_path)
        if resp.status < 300:
            print(f"  上传成功: {key}")
            return True
        else:
            print(f"  上传失败: {key}, 状态码: {resp.status}")
            return False
    except exception.ObsException as e:
        print(f"  上传异常: {e}")
        return False


def save_manifest(obs_client: ObsClient, bucket: str, prefix: str,
                  manifest: Dict[str, Any]) -> bool:
    """保存清单文件到 OBS"""
    import io

    manifest_key = f"{prefix}/manifest.json"
    content = json.dumps(manifest, indent=2)

    try:
        resp = obs_client.putContent(bucket, manifest_key, content)
        if resp.status < 300:
            print(f"\n清单已保存: obs://{bucket}/{manifest_key}")
            return True
        else:
            print(f"清单保存失败: {resp.status}")
            return False
    except exception.ObsException as e:
        print(f"清单保存异常: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='小型文件归档器 - 华为云 OBS 版本')
    parser.add_argument('--src-path', required=True, help='源文件目录')
    parser.add_argument('--bucket', required=True, help='OBS Bucket 名称')
    parser.add_argument('--prefix', required=True, help='OBS 路径前缀')
    parser.add_argument('--endpoint', help='OBS 端点 (如 obs.cn-north-4.myhuaweicloud.com)')
    parser.add_argument('--access-key', help='访问密钥 AK')
    parser.add_argument('--secret-key', help='访问密钥 SK')
    parser.add_argument('--workers', type=int, help='并行工作进程数')
    parser.add_argument('--tar-size-mb', type=int, default=20, help='tar 文件大小 (MB)')
    parser.add_argument('--scan-threads', type=int, default=8, help='文件扫描线程数')
    parser.add_argument('--no-md5', action='store_true', help='不计算 MD5')

    args = parser.parse_args()

    # 创建配置
    config = ObsArchiveConfig(
        bucket=args.bucket,
        prefix=args.prefix,
        endpoint=args.endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key,
        workers=args.workers,
        tar_size_mb=args.tar_size_mb,
        scan_threads=args.scan_threads,
        compute_md5=not args.no_md5
    )

    print(f"归档配置:")
    print(f"  源目录: {args.src_path}")
    print(f"  Bucket: {args.bucket}")
    print(f"  前缀: {args.prefix}")
    print(f"  工作进程: {config.workers}")
    print(f"  tar 大小: {args.tar_size_mb} MB")
    print(f"  计算 MD5: {config.compute_md5}")
    print()

    # 创建 OBS 客户端
    obs_client = config.get_obs_client()

    # 检查 Bucket 是否存在
    try:
        resp = obs_client.headBucket(args.bucket)
        if resp.status >= 300:
            print(f"Error: Bucket '{args.bucket}' 不存在或无权限")
            sys.exit(1)
    except exception.ObsException as e:
        print(f"Error: 无法访问 Bucket: {e}")
        sys.exit(1)

    # 扫描文件
    print("扫描文件...")
    file_queue = scan_files(args.src_path, config.scan_threads)

    file_count = file_queue.qsize()
    print(f"找到 {file_count} 个文件")
    print()

    if file_count == 0:
        print("没有文件需要归档")
        sys.exit(0)

    # 创建批次
    max_tar_size = args.tar_size_mb * 1024 * 1024
    batches: List[TarBatch] = []
    current_batch = TarBatch(len(batches))

    print("分组 tar 批次...")
    while not file_queue.empty():
        abs_path, rel_path, size = file_queue.get()

        md5 = None
        if config.compute_md5:
            print(f"  计算 MD5: {rel_path}")
            md5 = compute_md5(abs_path)

        file_entry = FileEntry(rel_path, abs_path, size, md5)

        if not current_batch.add(file_entry, max_tar_size):
            batches.append(current_batch)
            current_batch = TarBatch(len(batches))
            current_batch.add(file_entry, max_tar_size)

    if current_batch.files:
        batches.append(current_batch)

    print(f"分成 {len(batches)} 个 tar 文件")
    print()

    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix='archive_')
    print(f"临时目录: {temp_dir}")

    # 构建 tar 文件
    manifest = {
        "version": "1.0",
        "archive_date": datetime.utcnow().isoformat() + "Z",
        "source_path": args.src_path,
        "bucket": args.bucket,
        "prefix": args.prefix,
        "tar_count": len(batches),
        "file_count": file_count,
        "files": []
    }

    print("构建 tar 文件...")
    for batch in batches:
        print(f"  批次 {batch.batch_id}: {len(batch.files)} 个文件")
        tar_file = create_tar(batch, temp_dir)

        # 上传到 OBS
        obs_key = f"{args.prefix}/archive_{batch.batch_id:05d}.tar"
        upload_to_obs(obs_client, args.bucket, obs_key, tar_file)

        # 更新清单
        offset = 0
        for file_entry in batch.files:
            manifest["files"].append({
                "filename": file_entry.rel_path,
                "tar_key": obs_key,
                "offset": offset,
                "length": file_entry.size,
                "md5": file_entry.md5
            })
            offset += file_entry.size

        # 删除临时 tar 文件
        os.remove(tar_file)

    # 保存清单
    print()
    save_manifest(obs_client, args.bucket, args.prefix, manifest)

    # 清理
    os.rmdir(temp_dir)

    print()
    print("归档完成!")
    print(f"  文件总数: {file_count}")
    print(f"  tar 文件: {len(batches)}")


if __name__ == '__main__':
    main()
