#!/usr/bin/env bash
set -Eeuo pipefail

exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1

export DEBIAN_FRONTEND=noninteractive

# VPC hiện chỉ cấp IPv4; ép APT không chọn địa chỉ mirror IPv6 rồi bị timeout.
cat >/etc/apt/apt.conf.d/99force-ipv4 <<'EOF'
Acquire::ForceIPv4 "true";
EOF

retry() {
  local attempts=0
  local max_attempts=5
  until "$@"; do
    attempts=$((attempts + 1))
    if [[ "$attempts" -ge "$max_attempts" ]]; then
      echo "Command failed after $attempts attempts: $*"
      return 1
    fi
    sleep $((attempts * 5))
  done
}

retry apt-get update
retry apt-get upgrade -y
retry apt-get install -y ca-certificates curl git gnupg jq nginx snapd unzip

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

cat >/etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable
EOF

retry apt-get update
retry apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
systemctl enable --now nginx
usermod -aG docker ubuntu

if ! command -v certbot >/dev/null 2>&1; then
  snap install core
  snap refresh core
  snap install --classic certbot
  ln -sfn /snap/bin/certbot /usr/local/bin/certbot
fi

if ! command -v amazon-ssm-agent >/dev/null 2>&1; then
  snap install amazon-ssm-agent --classic
fi
if systemctl list-unit-files amazon-ssm-agent.service >/dev/null 2>&1; then
  systemctl enable --now amazon-ssm-agent.service
else
  systemctl enable --now snap.amazon-ssm-agent.amazon-ssm-agent.service
fi

mkdir -p /opt/${project_name}/app
chown -R ubuntu:ubuntu /opt/${project_name}
mkdir -p /var/www/letsencrypt

cat >/etc/nginx/conf.d/websocket-map.conf <<'EOF'
map $http_upgrade $connection_upgrade {
  default upgrade;
  ''      close;
}
EOF

rm -f /etc/nginx/sites-enabled/default
cat >/etc/nginx/sites-available/${project_name}.conf <<EOF
server {
  listen 80 default_server;
  listen [::]:80 default_server;
  server_name ${storefront_domain};

  client_max_body_size 20m;

  location ^~ /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$connection_upgrade;
    proxy_connect_timeout 10s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
  }
}

server {
  listen 80;
  listen [::]:80;
  server_name ${api_domain};

  client_max_body_size 20m;

  location ^~ /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }

  location /ws/chat/ {
    proxy_pass http://127.0.0.1:9001;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$connection_upgrade;
    proxy_connect_timeout 10s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
  }

  location / {
    proxy_pass http://127.0.0.1:9000;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$connection_upgrade;
    proxy_connect_timeout 10s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
  }
}

server {
  listen 80;
  listen [::]:80;
  server_name ${chatbot_domain};

  client_max_body_size 20m;

  location ^~ /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }

  location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$connection_upgrade;
    proxy_connect_timeout 10s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
  }
}
EOF

ln -sfn /etc/nginx/sites-available/${project_name}.conf /etc/nginx/sites-enabled/${project_name}.conf
nginx -t
systemctl reload nginx

cat >/usr/local/sbin/configure-${project_name}-tls <<'EOF'
#!/usr/bin/env bash
set -Eeuo pipefail

marker=/etc/nginx/.${project_name}-tls-configured
[[ -f "$marker" ]] && exit 0

certbot_contact_args=(--register-unsafely-without-email)
if [[ -n '${letsencrypt_email}' ]]; then
  certbot_contact_args=(--email '${letsencrypt_email}')
fi

certbot certonly \
  --webroot \
  --webroot-path /var/www/letsencrypt \
  --non-interactive \
  --agree-tos \
  --keep-until-expiring \
  "$${certbot_contact_args[@]}" \
  --cert-name '${api_domain}' \
  -d '${api_domain}' \
  -d '${storefront_domain}' \
  -d '${chatbot_domain}'

cat >/etc/nginx/sites-available/${project_name}.conf <<'NGINX'
server {
  listen 443 ssl;
  listen [::]:443 ssl;
  server_name ${storefront_domain};

  ssl_certificate /etc/letsencrypt/live/${api_domain}/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/${api_domain}/privkey.pem;
  client_max_body_size 20m;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 10s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
  }
}

server {
  listen 443 ssl;
  listen [::]:443 ssl;
  server_name ${api_domain};

  ssl_certificate /etc/letsencrypt/live/${api_domain}/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/${api_domain}/privkey.pem;
  client_max_body_size 20m;

  location /ws/chat/ {
    proxy_pass http://127.0.0.1:9001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 10s;
    proxy_read_timeout 86400s;
    proxy_send_timeout 86400s;
  }

  location / {
    proxy_pass http://127.0.0.1:9000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 10s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
  }
}

server {
  listen 443 ssl;
  listen [::]:443 ssl;
  server_name ${chatbot_domain};

  ssl_certificate /etc/letsencrypt/live/${api_domain}/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/${api_domain}/privkey.pem;
  client_max_body_size 20m;

  location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 10s;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
  }
}

server {
  listen 80;
  listen [::]:80;
  server_name ${storefront_domain} ${api_domain} ${chatbot_domain};

  location ^~ /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }

  location / {
    return 301 https://$host$request_uri;
  }
}
NGINX

nginx -t
systemctl reload nginx
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
cat >/etc/letsencrypt/renewal-hooks/deploy/reload-nginx <<'HOOK'
#!/usr/bin/env bash
set -Eeuo pipefail
nginx -t
systemctl reload nginx
HOOK
chmod 0755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx
touch "$marker"
EOF
chmod 0755 /usr/local/sbin/configure-${project_name}-tls

cat >/etc/systemd/system/${project_name}-tls.service <<EOF
[Unit]
Description=Issue Let's Encrypt certificate and enable HTTPS for ${project_name}
After=network-online.target nginx.service
Wants=network-online.target
ConditionPathExists=!/etc/nginx/.${project_name}-tls-configured

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/configure-${project_name}-tls
EOF

cat >/etc/systemd/system/${project_name}-tls.timer <<EOF
[Unit]
Description=Retry HTTPS configuration after DNS propagation

[Timer]
OnBootSec=2min
OnUnitInactiveSec=10min
Unit=${project_name}-tls.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now ${project_name}-tls.timer
systemctl enable --now certbot.timer || true
systemctl start ${project_name}-tls.service || true

CW_AGENT_DEB=/tmp/amazon-cloudwatch-agent.deb
curl -fsSL "https://amazoncloudwatch-agent-${aws_region}.s3.${aws_region}.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb" -o "$CW_AGENT_DEB"
dpkg -i -E "$CW_AGENT_DEB"

cat >/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'EOF'
{
  "agent": {
    "region": "${aws_region}",
    "run_as_user": "root"
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/cloud-init-output.log",
            "log_group_name": "${cloudwatch_log_group}",
            "log_stream_name": "{instance_id}/cloud-init",
            "retention_in_days": -1
          },
          {
            "file_path": "/var/log/user-data.log",
            "log_group_name": "${cloudwatch_log_group}",
            "log_stream_name": "{instance_id}/user-data",
            "retention_in_days": -1
          },
          {
            "file_path": "/var/log/nginx/access.log",
            "log_group_name": "${cloudwatch_log_group}",
            "log_stream_name": "{instance_id}/nginx-access",
            "retention_in_days": -1
          },
          {
            "file_path": "/var/log/nginx/error.log",
            "log_group_name": "${cloudwatch_log_group}",
            "log_stream_name": "{instance_id}/nginx-error",
            "retention_in_days": -1
          }
        ]
      }
    }
  }
}
EOF

/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

# Wait for files to be copied by Terraform provisioner
echo "Waiting for docker-compose.yml, init.sql, and .env to be uploaded..."
until [ -f /home/ubuntu/docker-compose.yml ] && [ -f /home/ubuntu/init.sql ] && [ -f /home/ubuntu/.env ]; do
  sleep 2
done

# Create app directory
APP_DIR="/opt/${project_name}/app"
mkdir -p "$APP_DIR/medusa-pubic"

# Move files to their correct destination
mv /home/ubuntu/docker-compose.yml "$APP_DIR/medusa-pubic/docker-compose.yml"
mv /home/ubuntu/init.sql "$APP_DIR/medusa-pubic/init.sql"
mv /home/ubuntu/.env "$APP_DIR/.env"
ln -sf "$APP_DIR/.env" "$APP_DIR/medusa-pubic/.env"
chown -R ubuntu:ubuntu "$APP_DIR"

# Terraform remote-exec sẽ start/restart Docker Compose sau khi bootstrap hoàn tất.
# Không chạy compose ở user_data để tránh 2 tiến trình cùng pull/start image trên máy mới.

cat >/etc/motd <<'EOF'
Managed by Terraform.
Deploy application files to /opt/${project_name}/app.
Backend ports must bind to 127.0.0.1 or an internal Docker network.
EOF

echo "Bootstrap completed successfully."
