```
sudo apt update && sudo apt upgrade -y
```

```
sudo apt install python3 python3-pip python3-venv -y
```

```
git clone https://github.com/Saimone2/trackinWalletsBot
cd trackinWalletsBot
```

```
sudo nano ./env

=======================================
TELEGRAM_TOKEN=...
ETHERSCAN_API_KEY=...
TRONGRID_API_KEY=...
=======================================
```

```
python3 -m venv venv
source venv/bin/activate
```

```
pip install python-telegram-bot ...
```

```
sudo nano /etc/systemd/system/scan-wallets-tg-bot.service

=======================================
[Unit]
Description=Scan Wallet Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/шлях/до/папки_бота
Environment=PATH=/шлях/до/папки_бота/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/шлях/до/папки_бота/venv/bin/python3 /шлях/до/папки_бота/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
=======================================
```


```
sudo systemctl daemon-reload

sudo systemctl start telegram-bot.service
sudo systemctl enable telegram-bot.service
sudo systemctl status telegram-bot.service
```