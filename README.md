
# 🎁 Discord Görsel Ödül Botu

Bu proje, Discord kullanıcılarına belirli aralıklarla bulanık (gizli) görseller gönderip, ilk tıklayan kullanıcının ödülü kazanmasını sağlayan bir interaktif oyun botudur.

## 📦 Proje Dosyaları

- `bot.py`: Discord botunun tüm komutlarını ve işleyişini kontrol eder.
- `logic.py`: SQLite veritabanı yönetimini ve görsel gizleme (pixelation) işlemlerini içerir.
- `config.py`: Bot token'ı ve veritabanı yolunu içerir. Güvenlik nedeniyle `.gitignore` içine alınmalıdır.

## 🚀 Özellikler

- `!start` komutuyla kullanıcı kaydı yapılır.
- Her dakika rastgele bir ödül görseli seçilir ve bulanıklaştırılarak kayıtlı kullanıcılara gönderilir.
- Görsel mesajında yer alan “🎁 Al!” butonuna ilk tıklayan kullanıcı, orijinal görselin sahibi olur.
- Kazananlar, veritabanına kaydedilir ve aynı ödül tekrar verilmez.
- Görseller `img/` klasöründen seçilir, bulanık hali `hidden_img/` klasöründe saklanır.

## 🗃 Veritabanı Yapısı

- **users**: `user_id`, `user_name`
- **prizes**: `prize_id`, `image`, `used`
- **winners**: `user_id`, `prize_id`, `win_time`

## 🖼 Görsel İşleme

Görseller `cv2` (OpenCV) ile bulanıklaştırılır ve sonra yeniden boyutlandırılarak piksel etkisi verilir.

## 🔧 Kurulum

1. Gerekli bağımlılıkları yükleyin:
   ```bash
   pip install discord.py opencv-python
   ```

2. `config.py` dosyasını düzenleyin:
   ```python
   TOKEN = 'your_bot_token_here'
   DATABASE = 'your_database_file.db'
   ```

3. Görselleri klasörlere yerleştirin:
   ```
   img/           -> Orijinal ödül görselleri
   hidden_img/    -> Bulanıklaştırılmış kopyalar buraya otomatik kaydedilir
   ```

4. Botu başlatın:
   ```bash
   python bot.py
   ```

## 📂 Klasör Yapısı

```
├── bot.py
├── logic.py
├── config.py
├── img/
│   └── ödül1.jpg
├── hidden_img/
│   └── ödül1.jpg (bulanık)
└── your_database_file.db
```

## 👤 Geliştirici

Bu proje, Python ile Discord botları geliştirme konusunda örnek teşkil etmesi amacıyla hazırlanmıştır. Herhangi bir sorunuz olursa iletişime geçmekten çekinmeyin!

---

## 📁 Kaynak Kodlar

### `bot.py`
```python
import discord
from discord.ext import commands, tasks
from logic import DatabaseManager, hide_img
from config import TOKEN, DATABASE
from discord.ui import Button, View

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

manager = DatabaseManager(DATABASE)
manager.create_tables()

# Kullanıcı kaydı komutu
@bot.command()
async def start(ctx):
    user_id = ctx.author.id
    if user_id in manager.get_users():
        await ctx.send("Zaten kayıtlısınız!")
    else:
        manager.add_user(user_id, ctx.author.name)
        await ctx.send("""Merhaba! Başarıyla kaydoldunuz! 🎉 Her dakika gizli bir resim alacaksınız ve 'Al!' butonuna ilk tıklayanlardan biri olursanız resmi kazanacaksınız!""")

# Resim gönderimi için görev
@tasks.loop(seconds = 1)
async def send_message():
    for user_id in manager.get_users():
        try:
            prize = manager.get_random_prize()
            prize_id, img, *_ = prize
            hide_img(img)
            user = await bot.fetch_user(user_id)
            if user:
                await send_image(user, f'hidden_img/{img}', prize_id)
            manager.mark_prize_used(prize_id)
        except:
            pass


# Resim ve buton gönderimi
async def send_image(user, image_path, prize_id):
    with open(image_path, 'rb') as img_file:
        file = discord.File(img_file)
        button = discord.ui.Button(label="Al!", custom_id=str(prize_id))
        view = ClaimView(prize_id)
        view.add_item(button)
        await user.send(file=file, view=view)



# Butona tıklanınca gerçek resmi gönder
@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data['custom_id']
        if custom_id.startswith("claim_"):
            prize_id = int(custom_id.split("_")[1])
            user_id = interaction.user.id
            img = manager.get_prize_img(prize_id)
            if manager.add_winner(user_id, prize_id):
                with open(f'img/{img}', 'rb') as original:
                    file = discord.File(original)
                    await interaction.response.send_message(file=file, content="🎉 Tebrikler! Resmi kazandınız!")
            else:
                await interaction.response.send_message(content="❌ Üzgünüm, bu resmi başkası aldı...", ephemeral=True)


class ClaimView(View):
    def __init__(self, prize_id):
        super().__init__(timeout=None)
        self.prize_id = prize_id
        self.add_item(Button(label="Al!", style=discord.ButtonStyle.primary, custom_id=f"claim_{prize_id}"))


# Bot hazır olduğunda başlat
@bot.event
async def on_ready():
    print(f'{bot.user} olarak giriş yapıldı!')
    if not send_message.is_running():
        send_message.start()

bot.run(TOKEN)

```

### `logic.py`
```python
import sqlite3
from datetime import datetime
from config import DATABASE 
import os
import cv2

class DatabaseManager:
    def __init__(self, database):
        self.database = database

    def create_tables(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT
            )
        ''')
            conn.execute('''
            CREATE TABLE IF NOT EXISTS prizes (
                prize_id INTEGER PRIMARY KEY,
                image TEXT,
                used INTEGER DEFAULT 0
            )
        ''')
            conn.execute('''
            CREATE TABLE IF NOT EXISTS winners (
                user_id INTEGER,
                prize_id INTEGER,
                win_time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
            )
        ''')
            conn.commit()

    def add_user(self, user_id, user_name):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('INSERT OR IGNORE INTO users VALUES (?, ?)', (user_id, user_name))
            conn.commit()

    def add_prize(self, data):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.executemany('INSERT INTO prizes (image) VALUES (?)', data)
            conn.commit()

    def add_winner(self, user_id, prize_id):
        win_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM winners WHERE user_id = ? AND prize_id = ?", (user_id, prize_id))
            if cur.fetchall():
                return 0
            else:
                conn.execute('INSERT INTO winners (user_id, prize_id, win_time) VALUES (?, ?, ?)', (user_id, prize_id, win_time))
                conn.commit()
                return 1

    def mark_prize_used(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('UPDATE prizes SET used = 1 WHERE prize_id = ?', (prize_id,))
            conn.commit()

    def get_users(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users")
            return [x[0] for x in cur.fetchall()]

    def get_prize_img(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT image FROM prizes WHERE prize_id = ?", (prize_id,))
            result = cur.fetchall()
            if result:
                return result[0][0]
            else:
                raise ValueError(f"{prize_id} ID'li ödül bulunamadı.")

    def get_random_prize(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM prizes WHERE used = 0 ORDER BY RANDOM()")
            result = cur.fetchall()
            if result:
                return result[0]
            else:
                raise ValueError("Kullanılabilir ödül kalmadı.")


def hide_img(img_name):
    image = cv2.imread(f'img/{img_name}')
    blurred_image = cv2.GaussianBlur(image, (15, 15), 0)
    pixelated_image = cv2.resize(blurred_image, (30, 30), interpolation=cv2.INTER_NEAREST)
    pixelated_image = cv2.resize(pixelated_image, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f'hidden_img/{img_name}', pixelated_image)

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()
    prizes_img = os.listdir('img')
    data = [(x,) for x in prizes_img]
    manager.add_prize(data)

    # Test için örnek çıktı
    print("Kayıtlı kullanıcılar:", manager.get_users())
    print("Rastgele ödül:", manager.get_random_prize())
    try:
        print("Ödül resmi:", manager.get_prize_img(1))
    except:
        print("1 numaralı ödül bulunamadı.")

```

### `config.py`
```python
TOKEN = 'your_token_here'
DATABASE = 'your_database_here'
```
