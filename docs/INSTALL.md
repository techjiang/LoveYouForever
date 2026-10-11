# 安装指南

给不太熟悉服务器的人写的。三种方式，挑一种。

---

## 方式一：一键脚本（推荐）

需要一台能上网的机器，装好 Python 3.9 以上。

```bash
git clone https://github.com/techjiang/LoveYouForever.git
cd LoveYouForever
bash install.sh
```

脚本会依次做这些事：

1. 检查 Python 版本
2. 问你要站点名、管理员账号密码（不想回答就一路回车，密码会自动生成）
3. 建虚拟环境、装依赖
4. 建目录、初始化数据库
5. 生成 `start.sh` / `start-prod.sh` / `backup.sh`

装完看到密码就记下来，然后：

```bash
./start.sh
```

访问 `http://127.0.0.1:5000`，后台在 `/admin`。

### 非交互安装

```bash
bash install.sh --yes --port 8080 --env production
```

### 参数

| 参数 | 说明 |
|---|---|
| `--yes` | 全部用默认值，不提问 |
| `--port 8080` | 指定端口 |
| `--env production` | 运行模式，`development` 或 `production` |
| `--no-venv` | 不用虚拟环境（已装好依赖时） |

---

## 方式二：Docker

```bash
git clone https://github.com/techjiang/LoveYouForever.git
cd LoveYouForever
docker compose up -d
```

看日志：`docker compose logs -f`

数据落在宿主机这几个目录，容器删掉也不会丢：

- `./instance` —— 数据库
- `./backups` —— 备份
- `./themes` —— 自定义主题
- `./app/static/uploads` —— 上传的图片

想加个密钥（生产环境建议）：

```bash
echo "LYF_SECRET_KEY=$(openssl rand -hex 32)" >> .env
docker compose up -d --force-recreate
```

---

## 方式三：手动

```bash
git clone https://github.com/techjiang/LoveYouForever.git
cd LoveYouForever

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env

flask --app wsgi:app init
flask --app wsgi:app create-admin   # 跟着提示走
python run.py
```

国内网络慢的话换镜像：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 放到公网

### Nginx 反代

```nginx
server {
    listen 80;
    server_name love.example.com;

    client_max_body_size 32m;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/LoveYouForever/app/static/;
        expires 30d;
    }
}
```

### HTTPS

```bash
sudo certbot --nginx -d love.example.com
```

### 用 systemd 常驻

`/etc/systemd/system/loveyouforever.service`：

```ini
[Unit]
Description=LoveYouForever
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/LoveYouForever
Environment="LYF_ENV=production"
ExecStart=/path/to/LoveYouForever/.venv/bin/gunicorn -w 4 -k gthread --threads 4 -b 127.0.0.1:5000 wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now loveyouforever
```

---

## 装完之后

1. **改密码** —— 后台「用户」页，或者 `flask --app wsgi:app reset-password`
2. **填站点地址** —— 后台「站点设置 → 基本信息」，绑定和 RSS 都靠它
3. **关掉注册** —— 「站点设置 → 互动与评论」，两个人的站不需要开放注册
4. **点一次备份** —— 后台「备份」页，先存个底
5. **加自动备份** —— 见下面

---

## 自动备份

```cron
0 3 * * * cd /path/to/LoveYouForever && ./backup.sh "每日自动备份" >> logs/backup.log 2>&1
```

编辑 crontab：`crontab -e`

---

## 换服务器

**旧服务器：**

```bash
flask --app wsgi:app backup --note "迁移"
# 或者
flask --app wsgi:app export --out migrate.json
```

**新服务器：** 装好之后把文件传过去

```bash
flask --app wsgi:app restore lyf-backup-xxx.tar.gz
# 或者
flask --app wsgi:app import migrate.json
```

---

## 出问题了？

```bash
flask --app wsgi:app doctor
```

会检查数据库、目录权限、用户数、情侣关系状态。

常见情况：

- **端口被占用** —— 换个端口
- **图片上传失败** —— 检查 `app/static/uploads/` 权限
- **忘了密码** —— `flask --app wsgi:app reset-password`
- **样式没生效** —— 强制刷新（Ctrl+Shift+R）清一下缓存

---

<div align="center">

**Powered by 科技酱 & LoveYouForever**

</div>
