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
