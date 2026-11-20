# 小型文件归档解决方案

[English](./README.md)

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## 简介

本解决方案用于将大量小型文件高效归档到华为云 OBS 对象存储，并通过清单文件实现单个文件的快速恢复。

### 核心功能

- **高效打包**: 将众多小文件打包成大型 tar 对象，大幅减少请求数量
- **清单管理**: 记录每个文件的 tar 路径和字节范围
- **快速恢复**: 支持直接从 tar 中提取单个文件，无需下载整个 tar
- **并行处理**: 多进程并行构建 tar 和上传，充分利用硬件资源
- **MD5 验证**: 可选计算并存储每个文件的 MD5 哈希值

### 解决的问题

- **请求费用**: 避免每个小文件产生一次 PUT 请求
- **存储费用**: 避免小型对象在 IA/Archive 存储类型的 128KB 最小结算限制

## 方案亮点

- 基于华为云 OBS 存储，提供标准对象存储 API
- 多进程并行处理，高吞吐量设计
- 简单可靠的 JSON 清单格式
- 支持单文件和多文件恢复

## 前置条件

- 华为云账号
- Python 3.9+
- OBS Bucket
- IAM 访问凭据

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置凭据

```bash
export HUAWEICLOUD_ACCESS_KEY="your-access-key"
export HUAWEICLOUD_SECRET_KEY="your-secret-key"
export HW_OBS_ENDPOINT="obs.cn-north-4.myhuaweicloud.com"
```

### 3. 归档文件

```bash
python src/archiver.py \
  --src-path /data/source_files \
  --bucket my-archive-bucket \
  --prefix archive/20260821
```

### 4. 恢复文件

```bash
python src/restorer.py \
  --bucket my-archive-bucket \
  --prefix archive/20260821 \
  --output /data/restored \
  --files file1.txt subdir/file2.txt
```

## 使用方法

### 归档器参数

| 参数 | 必填 | 说明 |
|------|------|------|
| --src-path | 是 | 源文件目录 |
| --bucket | 是 | OBS Bucket 名称 |
| --prefix | 是 | OBS 路径前缀 |
| --workers | 否 | 并行工作进程数 |
| --tar-size-mb | 否 | tar 文件大小 (MB) |
| --scan-threads | 否 | 文件扫描线程数 |

### 恢复器参数

| 参数 | 必填 | 说明 |
|------|------|------|
| --bucket | 是 | OBS Bucket 名称 |
| --prefix | 是 | 归档时的路径前缀 |
| --output | 是 | 恢复文件输出目录 |
| --files | 是 | 要恢复的文件名 |

### 完整参数列表

```bash
# 归档
python src/archiver.py --help

# 恢复
python src/restorer.py --help
```

## 部署

### Terraform 部署 OBS Bucket

```bash
cd infra
terraform init
terraform plan
terraform apply
```

### IAM 配置

需要创建 IAM 委托并授予以下权限:
- OBS: 读取和写入对象
- IAM: 读取委托信息

## 架构说明

```
┌──────────────┐    ┌────────────────┐    ┌───────────────┐
│ 文件源目录    │───>│ 归档器脚本     │───>│ OBS 存储     │
│              │    │ (多进程 tar)   │    │ (tar + 清单) │
└──────────────┘    └────────────────┘    └───────────────┘
```

详细架构说明请参考 [docs/architecture.md](docs/architecture.md)。

## 性能

| 指标 | 数值 |
|------|------|
| 吞吐量 | ~200 MB/s |
| 请求减少 | ~1000x |

## 涉及云服务

- OBS (对象存储服务)

## 清理资源

```bash
# 删除归档文件
obsutil rm obs://my-archive-bucket/archive/20260821/ -r

# 删除 Bucket
obsutil rb obs://my-archive-bucket -f
```

## 许可证

MIT No Attribution - Copyright (c) 2026 Huawei Cloud

## 联系方式

如有问题，请提交 Issue 或联系维护团队。
