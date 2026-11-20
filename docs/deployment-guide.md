# 部署指导书: 小型文件归档解决方案

## 1. 前置条件

### 1.1 华为云账号

- 已注册华为云账号
- 已完成实名认证

### 1.2 环境要求

| 要求 | 说明 |
|------|------|
| Python | 3.9 或更高版本 |
| pip | 最新版本 |
| 网络 | 能访问华为云 OBS 区域 |

### 1.3 必需的华为云资源

| 资源 | 说明 |
|------|------|
| OBS Bucket | 存储 tar 文件和清单 |
| IAM 委托 | 授予归档器读写 OBS 的权限 |

## 2. 资源创建

### 2.1 创建 OBS Bucket

通过控制台或 Terraform 创建 OBS Bucket:

```bash
# Terraform 方式 (infra/main.tf)
resource "huaweicloud_obs_bucket" "archive" {
  bucket     = "my-archive-bucket"
  storage_class = "STANDARD"
  multi_az   = true
}
```

### 2.2 创建 IAM 委托

1. 登录华为云控制台
2. 进入 IAM 控制台
3. 创建委托:
   - 名称: `archive-operator`
   - 策略: `OBS OperateAccess` 或自定义策略

## 3. 环境配置

### 3.1 安装依赖

```bash
pip install -r requirements.txt
```

### 3.2 配置凭据

设置华为云访问凭据 (选择一种):

**方式 1: 环境变量**
```bash
export HUAWEICLOUD_ACCESS_KEY="your-access-key"
export HUAWEICLOUD_SECRET_KEY="your-secret-key"
export HW_OBS_ENDPOINT="obs.cn-north-4.myhuaweicloud.com"
```

**方式 2: 配置文件**
```bash
# ~/.huaweicloud/config
[default]
access_key = your_access_key
secret_key = your_secret_key
region = cn-north-4
```

## 4. 使用方法

### 4.1 归档文件

```bash
python src/archiver.py \
  --src-path /data/source_files \
  --bucket my-archive-bucket \
  --prefix archive/20260821 \
  --workers 4 \
  --tar-size-mb 20
```

**参数说明**:

| 参数 | 必填 | 说明 |
|------|------|------|
| --src-path | 是 | 源文件目录 |
| --bucket | 是 | OBS Bucket 名称 |
| --prefix | 是 | OBS 路径前缀 |
| --workers | 否 | 并行工作进程数 (默认 CPU 核数) |
| --tar-size-mb | 否 | tar 文件大小 MB (默认 20) |
| --scan-threads | 否 | 文件扫描线程数 (默认 8) |
| --compute-md5 | 否 | 计算 MD5 (默认开启) |

### 4.2 恢复单个文件

```bash
python src/restorer.py \
  --bucket my-archive-bucket \
  --prefix archive/20260821 \
  --output /data/restored \
  --files file1.txt subdir/file2.txt
```

**参数说明**:

| 参数 | 必填 | 说明 |
|------|------|------|
| --bucket | 是 | OBS Bucket 名称 |
| --prefix | 是 | 归档时的路径前缀 |
| --output | 是 | 恢复文件输出目录 |
| --files | 是 | 要恢复的文件名 (可多个) |

### 4.3 列出归档文件

```bash
python src/lister.py \
  --bucket my-archive-bucket \
  --prefix archive/20260821
```

## 5. 验证

### 5.1 归档验证

归档完成后，检查:

1. OBS 中是否存在 tar 文件
2. 清单文件是否生成
3. 文件数量是否匹配

```bash
# 列出 OBS 中的 tar 文件
obsutil ls obs://my-archive-bucket/archive/20260821/

# 查看清单文件
obsutil cat obs://my-archive-bucket/archive/20260821/manifest.json
```

### 5.2 恢复验证

恢复后验证文件完整性:

```bash
# 验证 MD5
md5sum /data/restored/file1.txt
# 对比清单中的 MD5 值
```

## 6. 故障排除

### 6.1 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| 403 Forbidden | IAM 权限不足 | 检查委托策略 |
| 404 Not Found | Bucket 不存在 | 确认 Bucket 名称 |
| Connection Timeout | 网络问题 | 检查网络和端点 |

### 6.2 日志

启用调试日志:

```bash
python src/archiver.py --debug ...
```

## 7. 清理资源

### 7.1 删除归档文件

```bash
# 删除特定前缀的归档
obsutil rm obs://my-archive-bucket/archive/20260821/ -r
```

### 7.2 删除 OBS Bucket

```bash
# 先清空 Bucket
obsutil rb obs://my-archive-bucket -f
```

## 8. 性能优化

### 8.1 并行参数调优

| 场景 | 推荐配置 |
|------|----------|
| SSD 本地文件 | workers=CPU核数, scan-threads=16 |
| 网络文件系统 | workers=4, scan-threads=8 |
| 大文件 (GB级) | tar-size-mb=100, workers=2 |

### 8.2 网络优化

- 使用与 OBS 同区域的 ECS 运行归档器
- 避免跨区域访问
