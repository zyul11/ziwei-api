#!/bin/bash
BACKUP_DIR="/home/ubuntu/backups"
DB="/home/ubuntu/ziwei-api/data.db"
DATE=$(date +%Y%m%d)
mkdir -p "$BACKUP_DIR"
/home/ubuntu/ziwei-api/venv/bin/python -c "
import sqlite3
import shutil
src = '$DB'
dst = '$BACKUP_DIR/data_$DATE.db'
con = sqlite3.connect(src)
con.backup(sqlite3.connect(dst))
con.close()
print(f'Backed up to {dst}')
"
# 保留最近 30 天
find "$BACKUP_DIR" -name 'data_*.db' -mtime +30 -delete
