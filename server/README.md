# Fake GPS — сервер лицензий и Telegram-бот

## Перед первым запуском
Токен бота ранее отправлялся в переписку. Считайте его скомпрометированным: откройте @BotFather, отзовите старый токен через /revoke и получите новый. Не добавляйте токен в GitHub.

## Переменные окружения
Создайте локальный файл \`.env\` на основе \`.env.example\`:
- \`BOT_TOKEN\` — новый токен от @BotFather (секрет).
- \`ADMIN_IDS\` — Telegram ID владельца; в примере уже указан \`8264558707\`.
- \`DB_PATH\` — путь к SQLite базе. На хостинге укажите путь на постоянном диске.
- \`APP_DOWNLOAD_URL\` — необязательная ссылка на APK для кнопки в боте.
- \`PORT\` — локальный порт, по умолчанию 8000.

Файл \`.env\` и база данных исключены из Git через \`.gitignore\`.

## Локальный запуск
Python 3.11+:
\`\`\`bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python main.py
\`\`\`
Или используйте \`run_server.bat\` на Windows / \`run_server.sh\` на Linux и macOS.

## Render
Создайте Web Service из этого репозитория:
- Root Directory: \`server\`
- Build Command: \`pip install -r requirements.txt\`
- Start Command: \`uvicorn main:app --host 0.0.0.0 --port $PORT\`

Добавьте Environment Variables: \`BOT_TOKEN\`, \`ADMIN_IDS=8264558707\`, и \`DB_PATH=/var/data/keys.db\`.
Для сохранения SQLite базы подключите persistent disk, смонтированный в \`/var/data\`. Не используйте эфемерный диск для ключей: он может очищаться при перезапуске или redeploy. Для платёжного Telegram-бота используйте только один активный экземпляр polling-процесса.

## API приложения
- \`GET /health\` — проверка доступности.
- \`POST /api/activate\` — JSON: \`{"key":"FGPS-XXXX-XXXX-XXXX","device_id":"android-device-id"}\`.
- \`POST /api/status\` — такой же JSON.
Успех: \`valid\`, \`expires_at\`, \`now\`; ошибка: \`valid: false\`, \`message\`.

После развёртывания укажите публичный HTTPS URL сервера в Android \`Config.kt\`, без завершающего слеша. Telegram-бот: https://t.me/fakegps_bot.

## Важно
Этот сервер обслуживает выдачу/проверку лицензий и Telegram Stars. Перед реальными платежами выполните полный тест покупки, pre-checkout, выдачи ключа, активации, статуса и переноса на другое устройство. Не публикуйте токены, секреты или рабочую базу данных.
