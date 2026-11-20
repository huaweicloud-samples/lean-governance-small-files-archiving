# Small File Archiving Solution

[中文版](./README.cn.md)

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

This solution efficiently archives large numbers of small files to Huawei Cloud OBS (Object Storage Service) and enables fast single-file recovery through a manifest file.

### Core Features

- **Efficient Packaging**: Bundles many small files into large tar objects, significantly reducing API requests
- **Manifest Management**: Records each file's tar path and byte range
- **Fast Recovery**: Extracts individual files directly from tar without downloading the entire archive
- **Parallel Processing**: Multi-process parallel tar creation and upload for maximum throughput
- **MD5 Verification**: Optional MD5 hash calculation and storage for each file

### Problems Solved

- **Request charges**: avoid one PUT request per small file
- **Storage charges**: avoid the 128KB minimum billable size for IA/Archive storage classes

## Prerequisites

- Huawei Cloud account
- Python 3.9+
- OBS Bucket
- IAM credentials

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

```bash
export HUAWEICLOUD_ACCESS_KEY="your-access-key"
export HUAWEICLOUD_SECRET_KEY="your-secret-key"
export HW_OBS_ENDPOINT="obs.cn-north-4.myhuaweicloud.com"
```

### 3. Archive Files

```bash
python src/archiver.py \
  --src-path /data/source_files \
  --bucket my-archive-bucket \
  --prefix archive/20260821
```

### 4. Restore Files

```bash
python src/restorer.py \
  --bucket my-archive-bucket \
  --prefix archive/20260821 \
  --output /data/restored \
  --files file1.txt subdir/file2.txt
```

## Usage

### Archiver Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| --src-path | Yes | Source file directory |
| --bucket | Yes | OBS Bucket name |
| --prefix | Yes | OBS path prefix |
| --workers | No | Number of parallel workers |
| --tar-size-mb | No | Tar file size in MB |
| --scan-threads | No | File scan thread count |

### Restorer Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| --bucket | Yes | OBS Bucket name |
| --prefix | Yes | Archive path prefix |
| --output | Yes | Output directory for restored files |
| --files | Yes | File names to restore |

### Full Parameter List

```bash
# Archive
python src/archiver.py --help

# Restore
python src/restorer.py --help
```

## Deployment

### Deploy OBS Bucket with Terraform

```bash
cd infra
terraform init
terraform plan
terraform apply
```

### IAM Configuration

Create an IAM agency with the following permissions:
- OBS: Read and write objects
- IAM: Read agency information

## Architecture

```
┌──────────────┐    ┌────────────────┐    ┌───────────────┐
│ Source Dir   │───>│ Archiver       │───>│ OBS Storage  │
│              │    │ (Multi-process │    │ (tar + json) │
│              │    │  tar)          │    │              │
└──────────────┘    └────────────────┘    └───────────────┘
```

See [docs/architecture.md](docs/architecture.md) for detailed architecture.

## Performance

| Metric | Value |
|--------|-------|
| Throughput | ~200 MB/s |
| Request Reduction | ~1000x |

## Cloud Services

- OBS (Object Storage Service)

## Cleanup

```bash
# Delete archived files
obsutil rm obs://my-archive-bucket/archive/20260821/ -r

# Delete Bucket
obsutil rb obs://my-archive-bucket -f
```

## License

MIT No Attribution - Copyright (c) 2026 Huawei Cloud

## Contact

For issues, please submit an Issue or contact the maintenance team.
