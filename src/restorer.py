#!/usr/bin/env python3
"""
小型文件恢复器 - 华为云 OBS 版本

根据清单从 tar 中恢复单个文件。

Usage:
    python restorer.py --bucket my-bucket --prefix archive/20260821 --output /data/restored --files file1.txt
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

try:
    from obs import ObsClient, exception
except ImportError:
    print("Error: 请安装华为云 OBS SDK: pip install esdk-obs_python")
    sys.exit(1)


class ObsRestorerConfig:
    """OBS 恢复配置"""

    def __init__(self, bucket: str, prefix: str, endpoint: str,
                 access_key: str, secret_key: str):
        self.bucket = bucket
        self.prefix = prefix.rstrip('/')
        self.endpoint = endpoint or os.environ.get('HW_OBS_ENDPOINT', 'obs.cn-north-4.myhuaweicloud.com')
        self.access_key = os.environ.get('HUAWEICLOUD_ACCESS_KEY') if not access_key else access_key
        self.secret_key = os.environ.get('HUAWEICLOUD_SECRET_KEY') if not secret_key else secret_key

        if not self.access_key or not self.secret_key:
            raise ValueError("请设置 HUAWEICLOUD_ACCESS_KEY 和 HUAWEICLOUD_SECRET_KEY 环境变量或命令行参数")

    def get_obs_client(self) -> ObsClient:
        """创建 OBS 客户端"""
        return ObsClient(
            access_key_id=self.access_key,
            secret_access_key=self.secret_key,
            server=self.endpoint
        )


def load_manifest(obs_client: ObsClient, bucket: str, prefix: str) -> dict:
    """从 OBS 加载清单"""
    import io

    manifest_key = f"{prefix}/manifest.json"

    try:
        resp = obs_client.getObject(bucket, manifest_key)
        if resp.status < 300:
            content = resp.body.response.read()
            return json.loads(content)
        else:
            raise Exception(f"无法读取清单: {resp.status}")
    except exception.ObsException as e:
        raise Exception(f"加载清单失败: {e}")


def download_tar(obs_client: ObsClient, bucket: str, key: str, temp_dir: str) -> str:
    """下载 tar 文件到临时目录"""
    local_path = os.path.join(temp_dir, os.path.basename(key))

    try:
        resp = obs_client.getObject(bucket, key, downloadPath=local_path)
        if resp.status < 300:
            return local_path
        else:
            raise Exception(f"下载失败: {resp.status}")
    except exception.ObsException as e:
        raise Exception(f"下载异常: {e}")


def extract_file_from_tar(tar_path: str, file_name: str, output_dir: str) -> str:
    """从 tar 中提取单个文件"""
    import tarfile

    with tarfile.open(tar_path, 'r:*') as tar:
        member = tar.getmember(file_name)
        # 提取到临时文件
        temp_extract = tar.extractfile(member)
        if temp_extract is None:
            raise Exception(f"无法提取文件: {file_name}")

        # 创建输出目录
        output_path = Path(output_dir) / file_name
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(output_path, 'wb') as f:
            f.write(temp_extract.read())

        return str(output_path)


def verify_md5(file_path: str, expected_md5: str) -> bool:
    """验证 MD5"""
    md5_hash = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5_hash.update(chunk)

    actual_md5 = md5_hash.hexdigest()
    return actual_md5 == expected_md5


def main():
    parser = argparse.ArgumentParser(description='小型文件恢复器 - 华为云 OBS 版本')
    parser.add_argument('--bucket', required=True, help='OBS Bucket 名称')
    parser.add_argument('--prefix', required=True, help='归档时的路径前缀')
    parser.add_argument('--output', required=True, help='恢复文件输出目录')
    parser.add_argument('--files', nargs='+', required=True, help='要恢复的文件名')
    parser.add_argument('--endpoint', help='OBS 端点')
    parser.add_argument('--access-key', help='访问密钥 AK')
    parser.add_argument('--secret-key', help='访问密钥 SK')
    parser.add_argument('--verify', action='store_true', help='验证 MD5')

    args = parser.parse_args()

    # 创建配置
    config = ObsRestorerConfig(
        bucket=args.bucket,
        prefix=args.prefix,
        endpoint=args.endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key
    )

    print(f"恢复配置:")
    print(f"  Bucket: {args.bucket}")
    print(f"  前缀: {args.prefix}")
    print(f"  输出目录: {args.output}")
    print(f"  文件: {', '.join(args.files)}")
    print()

    # 创建 OBS 客户端
    obs_client = config.get_obs_client()

    # 加载清单
    print("加载清单...")
    try:
        manifest = load_manifest(obs_client, args.bucket, args.prefix)
        print(f"清单版本: {manifest.get('version')}")
        print(f"归档时间: {manifest.get('archive_date')}")
        print(f"文件总数: {len(manifest.get('files', []))}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    print()

    # 创建文件索引
    file_index = {f['filename']: f for f in manifest.get('files', [])}

    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix='restore_')
    print(f"临时目录: {temp_dir}")

    # 下载需要的 tar 文件
    tar_cache = {}
    success_count = 0

    for file_name in args.files:
        if file_name not in file_index:
            print(f"✗ 文件不存在: {file_name}")
            continue

        file_info = file_index[file_name]
        tar_key = file_info['tar_key']

        # 下载 tar (如果尚未下载)
        if tar_key not in tar_cache:
            print(f"下载 tar: {tar_key}")
            try:
                tar_path = download_tar(obs_client, args.bucket, tar_key, temp_dir)
                tar_cache[tar_key] = tar_path
            except Exception as e:
                print(f"  下载失败: {e}")
                continue

        # 提取文件
        try:
            tar_path = tar_cache[tar_key]
            output_path = extract_file_from_tar(tar_path, file_name, args.output)
            print(f"✓ 恢复: {file_name} -> {output_path}")

            # 验证 MD5
            if args.verify and file_info.get('md5'):
                if verify_md5(output_path, file_info['md5']):
                    print(f"  MD5 验证通过")
                else:
                    print(f"  ⚠ MD5 验证失败!")

            success_count += 1

        except Exception as e:
            print(f"✗ 提取失败: {file_name}, {e}")

    # 清理临时文件
    for tar_path in tar_cache.values():
        os.remove(tar_path)
    os.rmdir(temp_dir)

    print()
    print(f"恢复完成: {success_count}/{len(args.files)} 个文件")


if __name__ == '__main__':
    main()
